{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";
    python-dev.url = "git+http://git/mkpkgs/python-dev.git";
  };

  outputs = { self, ... }@inputs:
    with inputs;
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      stdenv = pkgs.stdenv;

      pythonPkgs = with pkgs.python3pkgs;
        (pkgs.python3.withPackages
          (python-pkgs: with python-pkgs; [ argcomplete ]));

      nativeBuildAndShellInputs = with pkgs; [ arduino-cli gup pythonPkgs ];

      tools = with pkgs; [ arduino-ide gdb graphviz plantuml ];
    in {
      packages.${system}.default = stdenv.mkDerivation {
        name = "planer_build";
        version = "0.1.0";

        src = ./.;

        installPhase = ''
          mkdir -p $out/bin
          cp sh/make_env $out/bin
        '';
      };

      hydraJobs = { inherit (self) packages; };

      devShells.${system}.default = pkgs.mkShell {
        nativeBuildInputs = nativeBuildAndShellInputs ++ tools
          ++ (with pkgs; [ clang-tools ]);
      };

      devShells.avr.default = let
        crossPkgs = import inputs.nixpkgs {
          localSystem = system;
          crossSystem = { config = "avr"; };
        };
      in crossPkgs.mkShell {
        nativeBuildInputs = nativeBuildAndShellInputs ++ tools;
        inputsFrom = [ inputs.python-dev.devShells.${system}.default ];

        shellHook = ''
          . sh/make_env
          # activate-global-python-argcomplete
        '';
      };
    };
}
