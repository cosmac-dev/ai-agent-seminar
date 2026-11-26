#!/bin/bash
# 仮想ディスプレイとデスクトップを起動し、ファイルマネージャとテキストエディタを並べて開く。コンテナが止まるまで待つ。
set -eu

if [[ "${1:-}" != "--in-session" ]]; then
  Xvfb "${DISPLAY}" -screen 0 1280x800x24 -nolisten tcp &
  until xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; do sleep 0.2; done
  # デスクトップとアプリを同じ D-Bus のセッションで動かすため、以降はセッションの中で実行する
  exec dbus-run-session -- "$0" --in-session
fi

# docker exec から起動するアプリ（第6節のダイアログなど）も同じセッションにつなげるよう、バスの場所を書き出す。
# つながないと、アプリが別のセッションと AT-SPI のバスを作り、アクセシビリティツリーがそちらに置き換わる
echo "${DBUS_SESSION_BUS_ADDRESS}" > /tmp/dbus-session-address
startxfce4 &
# パネルが表示されたらデスクトップの準備完了とみなす
until xdotool search --onlyvisible --class xfce4-panel >/dev/null 2>&1; do sleep 0.5; done

# 受信フォルダを Thunar で左に、経費一覧を Mousepad で右に並べて開く
place() {  # place <クラス名> <x> <幅>
  local wid
  until wid="$(xdotool search --onlyvisible --class "$1" | head -n 1)" && [[ -n "${wid}" ]]; do sleep 0.5; done
  xdotool windowmove "${wid}" "$2" 32 windowsize "${wid}" "$3" 730
}
thunar "${HOME}/受信" >/dev/null 2>&1 &
place thunar 0 560
mousepad "${HOME}/経費一覧.csv" >/dev/null 2>&1 &
place mousepad 565 715

# AT-SPI のバスの場所は X のルートウィンドウ（AT_SPI_BUS）に書かれる。docker exec からは、ここを見て要素を読む
until xprop -root AT_SPI_BUS 2>/dev/null | grep -q unix:; do sleep 0.5; done
touch /tmp/desktop-ready
wait
