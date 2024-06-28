{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";
    mk_build.url = "git+http://git/mk_build.git?ref=develop";
    dev.url = "git+http://git/mkpkgs/dev/dev.git";
  };

  outputs = { self, ... }@inputs:
    with inputs;
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      lib = pkgs.lib;
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

        propagatedBuildInputs = with python.pkgs; [
          argcomplete
          inputs.mk_build.packages.${system}.default
          setuptools
          tomlkit
        ];

        postInstall = ''
          mv $out/bin/planer $out/bin/planer1
        '';
      };

      shell = stdenv.mkDerivation {
        inherit version;

        name = "planer_shell";

        src = ./.;

        installPhase = ''
          mkdir -p $out/bin

          cp $src/sh/planer $out/bin

          cp -r $src/gup $out
          cp sh/planer_set_env $out/bin
        '';

        postInstall = with pkgs; ''
          wrapProgram $out/bin/planer \
            --set GUP $src \
            --prefix PATH : ${lib.makeBinPath [ gup ]}
        '';
      };
    in {
      packages.${system}.default = with pkgs;
        symlinkJoin {
          name = "planer_build";
          paths = [ pythonBuild shell direnv ];
        };

      hydraJobs = { inherit (self) packages; };

      devShells.${system}.default = let
        crossPkgs = import inputs.nixpkgs {
          localSystem = system;
          crossSystem = { config = "avr"; };
        };
      in crossPkgs.mkShell {
        nativeBuildInputs = nativeBuildAndShellInputs;
        inputsFrom = [ inputs.dev.devShells.${system}.python ];
      };
    };
}
