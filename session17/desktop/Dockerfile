# 第17回の仮想デスクトップ。エージェントが操作する Linux のデスクトップ（Xvfb + Xfce）を動かす。
# 中にはファイルマネージャ（Thunar）とテキストエディタ（Mousepad）、操作に使う道具が入っている。
#
# - 画面を撮る: ImageMagick の import
# - 入力する: xdotool（X11 に擬似的なマウス・キーボードの入力を送る。Windows の SendInput にあたる）
# - 画面の要素を読む: AT-SPI（Linux のアクセシビリティの仕組み。Windows の UI Automation にあたる）
#
# どれも `docker exec` で実行し、ホストの画面や入力デバイスには触れない。
# BuildKit がない環境（Dev Container の Docker CLI など）でもビルドできるよう、BuildKit 専用の記法は使わない。
# ビルド（session17/ で実行）:
#   docker build -f desktop/Dockerfile -t ai-agent-seminar-desktop:17 .

ARG BASE_IMAGE=debian:trixie-slim@sha256:8aa5a7bf5a1955bddbe7d74fcdd0b91ab30e74362a8b73af672b0481b35b44a0
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    LANG=ja_JP.UTF-8 \
    LC_ALL=ja_JP.UTF-8 \
    GTK_MODULES=gail:atk-bridge

# slim イメージは翻訳ファイルを入れない設定のため、日本語の翻訳だけは入れる（メニューなどを日本語にする）
RUN echo 'path-include /usr/share/locale/ja/*' > /etc/dpkg/dpkg.cfg.d/zz-locale-ja \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       xvfb x11-utils xdotool imagemagick \
       xfce4-session xfwm4 xfce4-panel xfdesktop4 xfce4-settings xfconf thunar dbus-x11 mousepad \
       at-spi2-core libatk-adaptor gir1.2-atspi-2.0 gir1.2-gtk-3.0 python3-gi \
       fonts-noto-cjk locales python3 \
    && sed -i 's/^# *ja_JP.UTF-8/ja_JP.UTF-8/' /etc/locale.gen && locale-gen \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash seminar

COPY desktop/start.sh /usr/local/bin/start-desktop
COPY desktop/a11y.py /usr/local/bin/a11y
COPY desktop/notice.py /usr/local/bin/notice
RUN chmod 0755 /usr/local/bin/start-desktop /usr/local/bin/a11y /usr/local/bin/notice

USER seminar
WORKDIR /home/seminar
# Xfce のパネルを既定の構成で用意する（ないと初回起動時に構成を選ぶダイアログが出る）。
# 下部のランチャー（2つ目のパネル）は外し、上部のタスクバーだけにする
RUN mkdir -p ~/.config/xfce4/xfconf/xfce-perchannel-xml \
    && sed '0,/<value type="int" value="2"\/>/{/<value type="int" value="2"\/>/d}' /etc/xdg/xfce4/panel/default.xml \
       > ~/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml
# Thunar を詳細表示にする（アイコン表示ではファイルが AT-SPI の要素として現れない）、テキストを Mousepad で開く
COPY --chown=seminar:seminar desktop/config/ /home/seminar/.config/
# 作業用のファイル（受信フォルダの領収書、経費一覧、処理済みフォルダ）
COPY --chown=seminar:seminar desktop/files/ /home/seminar/
RUN mkdir -p ~/処理済み

CMD ["start-desktop"]
