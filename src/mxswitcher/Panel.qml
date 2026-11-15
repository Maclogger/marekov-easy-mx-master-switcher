import QtQuick

// MX Master 4 Easy-Switch panel — a port of reference/linux/Panel.qml.
// `backend` (state, switching) and `theme` (colours) come from app.py.
Window {
  id: root
  flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
  color: "transparent"
  title: "MX Master 4"
  width: 340
  height: frame.implicitHeight

  property bool shown: false
  readonly property string fontFamily: "JetBrainsMono Nerd Font"

  property bool connected: false
  property int current: 0
  property int here: 0
  property int awayTo: 0
  property int count: 3
  property var names: ({})
  property bool lanMouse: false
  readonly property bool switching: backend.switching
  property int cursorIndex: 0
  property bool cursorActive: false

  readonly property string icon: connected ? "󰍽" : "󰍾"

  readonly property string statusText: {
    if (switching) return "Switching…"
    if (connected) return "On this computer · device " + current
    if (awayTo > 0) return "Away · on " + channelLabel(awayTo)
    return "Not connected"
  }

  function hostName(channel) {
    var name = names[String(channel)]
    return name ? String(name).slice(0, 48) : ""
  }

  function channelLabel(channel) {
    return hostName(channel) || "device " + channel
  }

  function buttonText(channel) {
    var text = hostName(channel) ? channel + "   " + hostName(channel) : channel + "   Device " + channel
    return channel === here ? text + "  (this computer)" : text
  }

  function apply(raw) {
    var state
    try { state = JSON.parse(String(raw || "")) } catch (e) { return }
    if (!state || typeof state !== "object") return
    connected = state.connected === true
    count = Math.max(1, Math.min(6, parseInt(state.count) || 3))
    current = parseInt(state.current) || 0
    here = parseInt(state.here) || 0
    awayTo = connected ? 0 : (parseInt(state.awayTo) || 0)
    names = state.names && typeof state.names === "object" ? state.names : ({})
    lanMouse = state.lanMouse === true
  }

  function switchTo(channel) {
    if (!connected || switching || channel === current) return
    backend.switchTo(channel)
  }

  function moveCursor(delta) {
    if (!cursorActive) { cursorActive = true; return }
    cursorIndex = (cursorIndex + delta + count + 1) % (count + 1)  // the last row is lan-mouse
  }

  function activate() {
    if (!cursorActive) return
    if (cursorIndex === count) backend.setLanMouse(!lanMouse)
    else switchTo(cursorIndex + 1)
  }

  Component.onCompleted: apply(backend.stateJson)
  Connections {
    target: backend
    function onStateJsonChanged() { root.apply(backend.stateJson) }
  }

  onShownChanged: {
    if (shown) {
      cursorActive = false
      cursorIndex = Math.max(0, current - 1)
      closeAnim.stop()
      visible = true
      raise()
      requestActivate()
      frame.forceActiveFocus()
      openAnim.restart()
    } else {
      openAnim.stop()
      closeAnim.restart()
    }
  }
  onActiveChanged: if (!active) shown = false

  ParallelAnimation {
    id: openAnim
    NumberAnimation { target: frame; property: "opacity"; from: 0; to: 1; duration: 180; easing.type: Easing.OutCubic }
    NumberAnimation { target: frame; property: "scale"; from: 0.97; to: 1; duration: 180; easing.type: Easing.OutCubic }
  }

  SequentialAnimation {
    id: closeAnim
    ParallelAnimation {
      NumberAnimation { target: frame; property: "opacity"; to: 0; duration: 120; easing.type: Easing.OutCubic }
      NumberAnimation { target: frame; property: "scale"; to: 0.97; duration: 120; easing.type: Easing.OutCubic }
    }
    ScriptAction { script: root.visible = false }
  }

  Rectangle {
    id: frame
    width: root.width
    implicitHeight: column.implicitHeight + 2 * column.y
    transformOrigin: Item.Bottom
    color: theme.background
    border.color: theme.accent
    border.width: 2
    radius: 2
    focus: true

    Keys.onEscapePressed: root.shown = false
    Keys.onUpPressed: root.moveCursor(-1)
    Keys.onDownPressed: root.moveCursor(1)
    Keys.onReturnPressed: root.activate()
    Keys.onEnterPressed: root.activate()

    Column {
      id: column
      x: 18
      y: 18
      width: parent.width - 2 * x
      spacing: 14

      // Hero
      Row {
        spacing: 14
        Text {
          anchors.verticalCenter: parent.verticalCenter
          textFormat: Text.PlainText
          text: root.icon
          color: theme.foreground
          opacity: root.connected ? 1.0 : 0.5
          font.family: root.fontFamily
          font.pixelSize: 30
        }
        Column {
          spacing: 3
          Text {
            textFormat: Text.PlainText
            text: "MX Master 4"
            color: theme.foreground
            font.family: root.fontFamily
            font.pixelSize: 17
            font.bold: true
          }
          Text {
            textFormat: Text.PlainText
            text: root.statusText.toUpperCase()
            color: theme.dim
            font.family: root.fontFamily
            font.pixelSize: 11
            font.letterSpacing: 1.2
          }
        }
      }

      Rectangle { width: parent.width; height: 1; color: theme.rowBorder; opacity: 0.6 }

      Column {
        width: parent.width
        spacing: 8

        Text {
          textFormat: Text.PlainText
          text: "Easy-Switch"
          color: theme.foreground
          opacity: 0.8
          font.family: root.fontFamily
          font.pixelSize: 12
          font.bold: true
        }

        Repeater {
          model: root.count

          Rectangle {
            required property int index
            readonly property int channel: index + 1
            readonly property bool active: channel === (root.connected ? root.current : root.awayTo)
            readonly property bool hasCursor: root.cursorActive && root.cursorIndex === index
            width: parent.width
            height: 40
            enabled: root.connected && !root.switching
            opacity: enabled || active ? 1.0 : 0.55
            color: active ? theme.selection : "transparent"
            border.width: 1
            border.color: hasCursor && enabled ? theme.accent : theme.rowBorder
            Behavior on border.color { ColorAnimation { duration: 90 } }

            Row {
              x: 14
              anchors.verticalCenter: parent.verticalCenter
              spacing: 12
              Text {
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                text: parent.parent.channel === root.here ? "󰌢" : "󰍹"
                color: theme.foreground
                font.family: root.fontFamily
                font.pixelSize: 17
              }
              Text {
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                text: root.buttonText(parent.parent.channel)
                color: theme.foreground
                font.family: root.fontFamily
                font.pixelSize: 13
              }
            }

            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onEntered: {
                root.cursorActive = true
                root.cursorIndex = parent.index
              }
              onClicked: root.switchTo(parent.channel)
            }
          }
        }
      }

      Column {
        width: parent.width
        spacing: 8

        Text {
          textFormat: Text.PlainText
          text: "Lan Mouse"
          color: theme.foreground
          opacity: 0.8
          font.family: root.fontFamily
          font.pixelSize: 12
          font.bold: true
        }

        Rectangle {
          id: lanRow
          readonly property bool hasCursor: root.cursorActive && root.cursorIndex === root.count
          width: parent.width
          height: 40
          color: root.lanMouse ? theme.selection : "transparent"
          border.width: 1
          border.color: hasCursor ? theme.accent : theme.rowBorder
          Behavior on border.color { ColorAnimation { duration: 90 } }

          Row {
            x: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12
            Text {
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: root.lanMouse ? "󰌘" : "󰌙"
              color: theme.foreground
              font.family: root.fontFamily
              font.pixelSize: 17
            }
            Text {
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: root.lanMouse ? "Receiving from Linux" : "Off"
              color: theme.foreground
              font.family: root.fontFamily
              font.pixelSize: 13
            }
          }

          // Switch
          Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            width: 34
            height: 18
            radius: 9
            color: root.lanMouse ? theme.accent : "transparent"
            border.width: 1
            border.color: root.lanMouse ? theme.accent : theme.dim
            Behavior on color { ColorAnimation { duration: 120 } }

            Rectangle {
              width: 12
              height: 12
              radius: 6
              anchors.verticalCenter: parent.verticalCenter
              x: root.lanMouse ? parent.width - width - 3 : 3
              color: root.lanMouse ? theme.background : theme.dim
              Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
            }
          }

          MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: {
              root.cursorActive = true
              root.cursorIndex = root.count
            }
            onClicked: backend.setLanMouse(!root.lanMouse)
          }
        }
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.Wrap
        text: root.connected
          ? "Shortcut: Ctrl + Alt + Shift + 1 / 2 / 3"
          : "The mouse is on another computer. Switch it back from there (or with its Easy-Switch button)."
        color: theme.dim
        font.family: root.fontFamily
        font.pixelSize: 11
        lineHeight: 1.2
      }
    }
  }
}
