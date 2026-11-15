"""State cache, status and switching — the same logic as mx-host's status() / switch()."""
import json
import logging
import os

from .hidpp import HidppError, Mouse, Unreachable

APP_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'MarekovEasyMxMasterSwitcher')
CACHE = os.path.join(APP_DIR, 'state.json')

log = logging.getLogger(__name__)


def load_cache():
    try:
        with open(CACHE, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(**data):
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(CACHE + '.new', 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(CACHE + '.new', CACHE)
    except OSError:
        pass


def label(names, channel):
    name = names.get(str(channel), '')
    return f'{channel} · {name}' if name else str(channel)


def cached_state():
    cache = load_cache()
    return {
        'connected': False,
        'current': None,
        'count': cache.get('count', 3),
        'names': cache.get('names', {}),
        'here': cache.get('here'),
        'awayTo': cache.get('awayTo'),
        'error': '',
    }


def status():
    """Live state while the mouse is here; the cached channel list while it is away."""
    state = cached_state()
    try:
        with Mouse() as mouse:
            count, current = mouse.channels()
            # Names only change on re-pairing, so read them once per channel layout.
            if not state['names'] or state['count'] != count or state['here'] != current:
                state['names'] = mouse.names(count) or state['names']
                log.info('channels %s, names %s', count, state['names'])
    except (Unreachable, *HidppError) as e:
        state['error'] = str(e)
        return state
    state.update(connected=True, count=count, current=current, here=current, awayTo=None)
    save_cache(count=count, names=state['names'], here=current)
    return state


def switch(channel, notify):
    """Send the mouse to `channel`; notify(title, body) reports what happened."""
    try:
        with Mouse() as mouse:
            count, current = mouse.channels()
            if not 1 <= channel <= count:
                notify('MX Master 4', f'There is no channel {channel} (1–{count}).')
                return
            names = load_cache().get('names') or mouse.names(count)
            if channel == current:
                notify('MX Master 4', f'Already on this computer ({label(names, channel)}).')
                return
            notify(f'MX Master 4 → device {channel}', f'Moved to {label(names, channel)}.')
            mouse.switch_to(channel)
    except Unreachable as e:
        notify('MX Master 4 is not here', f'Cannot switch it: {e}.')
        return
    except HidppError as e:
        notify('MX Master 4 switch failed', str(e))
        return
    log.info('switched %s -> %s', current, channel)
    save_cache(count=count, names=names, here=current, awayTo=channel)
