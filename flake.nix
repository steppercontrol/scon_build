{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";
    dev.url = "git+http://git/mkpkgs/dev/dev.git";
  };

  outputs = { self, ... }@inputs:
    with inputs;
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      stdenv = pkgs.stdenv;
      python = pkgs.python3;
      pythonPkgs = python.python3pkgs;

      pythonTools = with pythonPkgs;
        (pkgs.python3.withPackages
          (python-pkgs: with python-pkgs; [ argcomplete ]));

      nativeBuildAndShellInputs = with pkgs; [ arduino-cli gup pythonTools ];

      version = "0.1.0";

      pythonBuild = python.pkgs.buildPythonApplication {
        inherit version;

        pname = "planer_build";
        format = "pyproject";

        src = ./python;

        propagatedBuildInputs = with python.pkgs; [ setuptools tomlkit ];
      };

      shell = stdenv.mkDerivation {
        inherit version;

        name = "planer_shell";

        src = ./.;

        installPhase = ''
          mkdir -p $out/bin
          cp sh/planer_set_env $out/bin
        '';
      };
    in {
      packages.${system}.default = pkgs.symlinkJoin {
        name = "planer_build";
        paths = [ pythonBuild shell ];
      };

      hydraJobs = { inherit (self) packages; };

      devShells.${system}.default = pkgs.mkShell {
        nativeBuildInputs = nativeBuildAndShellInputs;
        inputsFrom = [ inputs.dev.devShells.${system}.python ];
      };
    };
}
