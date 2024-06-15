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

      nativeBuildAndShellInputs = with pkgs; [ arduino-cli gup ];

      tools = with pkgs; [ arduino-ide gdb graphviz plantuml ];
    in {
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
      };
    };
}
