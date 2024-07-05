{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";
    mk_build.url = "github:fmahnke/mk_build?ref=develop";
    dev.url = "github:fmahnke/mkpkgs-dev";
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

      nativeBuildAndShellInputs = with pkgs; [
        arduino-cli
        gup
        jq # for planer_set_env
        pythonTools
      ];

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

        postInstall = with pkgs; ''
          wrapProgram $out/bin/planer \
            --set GUP $src \
            --prefix PATH : ${lib.makeBinPath [ arduino-cli gup ]}
        '';
      };

      shell = with pkgs;
        stdenv.mkDerivation {
          inherit version;

          name = "planer_shell";

          src = ./.;

          nativeBuildInputs = [ makeWrapper ];

          installPhase = ''
            runHook preInstall

            echo pythonpath ${inputs.mk_build.packages.${system}.default}

            mkdir -p $out/bin

            cp sh/planer_set_env $out/bin

            runHook postInstall
          '';

          postInstall = ''
            wrapProgram $out/bin/planer_set_env \
              --prefix PATH : ${lib.makeBinPath [ jq ]}
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
      in with pkgs;
      crossPkgs.mkShell {
        nativeBuildInputs = nativeBuildAndShellInputs ++ [ direnv ];
        inputsFrom = [ inputs.dev.devShells.${system}.python ];

        shellHook = ''
          eval "$(${direnv}/bin/direnv hook bash)"
        '';
      };
    };
}
