
{ pkgs }: {
  deps = [
    pkgs.python312Full
    pkgs.python312Packages.pip
    pkgs.python312Packages.setuptools
    pkgs.python312Packages.wheel
    
    # Playwright browser dependencies
    pkgs.chromium
    pkgs.firefox
    
    # System libraries for Chromium
    pkgs.nspr
    pkgs.nss
    pkgs.dbus
    pkgs.atk
    pkgs.at-spi2-atk
    pkgs.expat
    pkgs.at-spi2-core
    pkgs.xorg.libXcomposite
    pkgs.xorg.libXdamage
    pkgs.xorg.libXfixes
    pkgs.mesa
    pkgs.xorg.libxcb
    pkgs.libxkbcommon
    pkgs.systemd
    pkgs.alsa-lib
    
    # System libraries for Firefox
    pkgs.xorg.libXcb
    pkgs.xorg.libxcb
    pkgs.xorg.libXcomposite
    pkgs.xorg.libXdamage
    pkgs.xorg.libXfixes
    pkgs.gtk3
    pkgs.pango
    pkgs.atk
    pkgs.cairo
    pkgs.gdk-pixbuf
    pkgs.xorg.libXrender
    pkgs.freetype
    pkgs.fontconfig
    pkgs.dbus
    
    # System libraries for WebKit
    pkgs.gstreamer
    pkgs.gtk4
    pkgs.pango
    pkgs.harfbuzz
    pkgs.gdk-pixbuf
    pkgs.cairo
    pkgs.vulkan-loader
    pkgs.icu
    pkgs.libxml2
    pkgs.sqlite
    pkgs.libxslt
    pkgs.lcms2
    pkgs.libvpx
    pkgs.libevent
    pkgs.libopus
    pkgs.libgcrypt
    pkgs.libgpg-error
    pkgs.gst_all_1.gstreamer
    pkgs.gst_all_1.gst-plugins-base
    pkgs.gst_all_1.gst-plugins-good
    pkgs.gst_all_1.gst-plugins-bad
    pkgs.webp
    pkgs.libavif
    pkgs.libjpeg
    pkgs.libpng
    pkgs.enchant
    pkgs.libsecret
    pkgs.libtasn1
    pkgs.hyphen
    pkgs.wayland
    pkgs.libdrm
    pkgs.libpsl
    pkgs.nghttp2
    pkgs.mesa
    pkgs.x264
    
    # Additional dependencies
    pkgs.xorg.libX11
    pkgs.xorg.libXext
    pkgs.xorg.libXrandr
    pkgs.xorg.libXi
    pkgs.xorg.libXtst
    pkgs.xorg.libXcursor
    pkgs.xorg.libXScrnSaver
    pkgs.xvfb-run
  ];
  
  env = {
    PYTHON_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.stdenv.cc.cc.lib
      pkgs.zlib
      pkgs.glib
      pkgs.nss
      pkgs.nspr
      pkgs.dbus
      pkgs.atk
      pkgs.at-spi2-atk
      pkgs.gtk3
      pkgs.pango
      pkgs.cairo
      pkgs.gdk-pixbuf
      pkgs.xorg.libX11
      pkgs.xorg.libXcomposite
      pkgs.xorg.libXdamage
      pkgs.xorg.libXext
      pkgs.xorg.libXfixes
      pkgs.xorg.libXrandr
      pkgs.xorg.libxcb
      pkgs.mesa
      pkgs.expat
      pkgs.libxkbcommon
      pkgs.alsa-lib
      pkgs.at-spi2-core
    ];
    PYTHONBIN = "${pkgs.python312Full}/bin/python3.12";
    LANG = "en_US.UTF-8";
    DISPLAY = ":99";
    PLAYWRIGHT_BROWSERS_PATH = "/nix/store";
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1";
  };
}
