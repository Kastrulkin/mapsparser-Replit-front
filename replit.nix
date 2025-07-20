
{ pkgs }: {
  deps = [
    pkgs.python312Full
    pkgs.python312Packages.pip
    pkgs.python312Packages.setuptools
    pkgs.python312Packages.wheel
  ];
  
  env = {
    PYTHON_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      # Add any specific libraries if needed
    ];
    PYTHONBIN = "${pkgs.python312Full}/bin/python3.12";
    LANG = "en_US.UTF-8";
  };
}
