{ pkgs }: {
  deps = [
    pkgs.chromium
    pkgs.xvfb-run
    pkgs.nspr
    pkgs.nss
    pkgs.dbus
    pkgs.atk
    pkgs.at-spi2-atk
    pkgs.cups
    pkgs.expat
    pkgs.libxcb
    pkgs.libxkbcommon
    pkgs.at-spi2-core
    pkgs.libXcomposite
    pkgs.libXdamage
    pkgs.libXfixes
    pkgs.mesa
    pkgs.cairo
    pkgs.pango
    pkgs.systemd
    pkgs.alsa-lib
    pkgs.glib
    pkgs.gtk3
    pkgs.libdrm
  ];
}