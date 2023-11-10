from typing import Optional, TypedDict
import yaml
import os
from rich.console import Console
import subprocess
import argparse


class Option(TypedDict):
    flag: str
    value: any


class Command(TypedDict):
    title: str
    options: list[Option]
    output_extension: str
    output_filename_suffix: str
    command: list[str]


class Config(TypedDict):
    ffmpeg_path: str
    commands: list[Command]


class StartupChecker:
    def __init__(self) -> None:
        self.result = None
        self.check_config()
        self.config = self.load_config()
        self.check_ffmpeg_executable()

    def __print_check_message(self, message: str, is_ok: bool):
        """
        Print a check message with a colored OK or NG label.

        Args:
            message (str): The message to be printed.
            is_ok (bool): A boolean indicating whether the check passed or not.
        """
        Console().print(
            f"[[{'green' if is_ok else 'red'}]{'  OK  ' if is_ok else '  NG  '}[/{'green' if is_ok else 'red'}]] {message}"
        )

    def check_config(self):
        """
        Check if the config.yaml file exists. If not, create it and print a message.
        If it exists, print a message indicating that it was found.
        """
        if not os.path.isfile("config.yaml"):
            self.create_config()
            self.__print_check_message(
                f"config.yaml not found. -> created at {os.path.join(os.path.dirname(__file__), 'config.yaml')}",
                False,
            )
            self.result = False
        else:
            self.__print_check_message("config.yaml found.", True)
            self.result = True

    def create_config(self):
        with open("config.yaml", "w") as f:
            yaml.dump(
                {
                    "ffmpeg_path": "/usr/bin/ffmpeg",
                    "commands": [
                        {
                            "title": "Make video lighter by using h264_nvenc CQ 32",
                            "options": [
                                {"flag": "-cq", "value": 32},
                                {"flag": "-c:v", "value": "h264_nvenc"},
                            ],
                            "output_extension": ".mp4",
                            "output_filename_suffix": "_light",
                            "command": [
                                "{{ffmpeg_path}}",
                                "-i",
                                "{{input_path}}",
                                "{{options}}",
                                "{{output_path}}",
                            ],
                        }
                    ],
                },
                f,
                default_flow_style=False,
            )

    def load_config(self):
        with open("config.yaml", "r") as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    def get_config(self) -> Config:
        return self.config

    def check_ffmpeg_executable(self):
        if not os.path.isfile(self.config["ffmpeg_path"]):
            self.__print_check_message(
                f"ffmpeg executable not found at {self.config['ffmpeg_path']}", False
            )
            self.result = False
        else:
            self.__print_check_message(
                f"ffmpeg executable found at {self.config['ffmpeg_path']}", True
            )
            self.result = True


class Runner:
    def __init__(self, config: Config, args: argparse.Namespace) -> None:
        self.config = config
        self.args = args

    def __print_message(self, message: str, is_from_system: bool):
        Console().print(
            f"[[{'yellow' if is_from_system else 'blue'}]{'SYSTEM' if is_from_system else ' USER '}[/{'yellow' if is_from_system else 'blue'}]] {message}"
        )

    def run(self):
        if self.args.config:
            self.__print_message(
                f"config.yaml path is {os.path.join(os.path.dirname(__file__), 'config.yaml')}",
                True,
            )
            Console().print(self.config)
            exit(0)
        command: Command = self.__choose_command()
        input_path: str = self.__ask_input_path()
        options: list[Option] = self.__modify_options(command["options"])
        output_path: str = self.__modify_output_path(command, input_path)
        self.__execute_command(command, input_path, options, output_path)

    def __choose_command(self) -> Command:
        self.__print_message("Choose a command.", True)
        for i, command in enumerate(self.config["commands"]):
            Console().print(f"    [green]{i}[/green]: {command['title']}")
        choice = int(Console().input("[green]Choice > [/green]"))
        self.__print_message(
            f"Chosen command: {self.config['commands'][choice]['title']}", False
        )
        print()
        return self.config["commands"][choice]

    def __ask_input_path(self) -> str:
        self.__print_message("Input the path of the video file.", True)
        input_path = Console().input("[green]Input path > [/green]")
        self.__print_message(f"Input path: {input_path}", False)
        print()
        return input_path

    def __modify_options(self, options: list[Option]) -> list[Option]:
        self.__print_message("Options are below. Is it OK?", True)
        for i, option in enumerate(options):
            Console().print(f"    {option['flag']} {option['value']}")
        choice = Console().input("[green]y/n > [/green]")

        if choice == "n":
            self.__print_message("Choose option you want to modify.", True)
            for i, option in enumerate(options):
                Console().print(
                    f"    [green]{i}[/green]: {option['flag']} {option['value']}"
                )
            choice = int(Console().input("[green]Choice > [/green]"))
            self.__print_message(
                f"Chosen option: {options[choice]['flag']} {options[choice]['value']}",
                False,
            )
            self.__print_message("Input new value.", True)
            new_value = Console().input("[green]New value > [/green]")
            self.__print_message(f"New value: {new_value}", False)
            options[choice]["value"] = new_value

            self.__modify_options(options)
        return options

    def __modify_output_path(self, command: Command, input_path: str) -> str:
        print()
        self.__print_message(
            "Current output path is: "
            + os.path.join(
                os.getcwd(),
                f"{os.path.splitext(input_path)[0]}{command['output_filename_suffix']}{command['output_extension']}",
            ),
            True,
        )
        self.__print_message("Is it OK?", True)
        choice = Console().input("[green]y/n > [/green]")
        if choice == "n":
            self.__print_message("Input new output path.", True)
            output_path = Console().input("[green]Output path: [/green]")
            self.__print_message(f"Output path: {output_path}", False)
            return output_path
        else:
            return os.path.join(
                os.getcwd(),
                f"{os.path.splitext(input_path)[0]}{command['output_filename_suffix']}{command['output_extension']}",
            )

    def __execute_command(
        self, command: Command, input_path: str, options: list[Option], output_path: str
    ):
        print()
        command_list = command["command"]
        command_list[command_list.index("{{ffmpeg_path}}")] = self.config["ffmpeg_path"]
        command_list[command_list.index("{{input_path}}")] = input_path
        command_list[command_list.index("{{output_path}}")] = output_path
        command_list[command_list.index("{{options}}")] = " ".join(
            [f"{option['flag']} {option['value']}" for option in options]
        )
        self.__print_message("Generated command:", True)
        Console().print(" ".join(command_list))
        self.__print_message("Do you want to execute this command?", True)
        choice = Console().input("[green]y/n: [/green]")
        if choice == "y":
            self.__print_message("Executing command...", True)
            subprocess.run(command_list)
            self.__print_message("Done.", True)
        else:
            self.__print_message("Aborted.", True)


if __name__ == "__main__":
    startup_checker = StartupChecker()
    if startup_checker.result:
        print("Startup check passed.\n")
    else:
        print("Startup check failed.")
        exit(1)

    parser = argparse.ArgumentParser("kffmpeg", description="A simple ffmpeg wrapper.")
    parser.add_argument("-v", "--version", action="version", version="kffmpeg 0.0.1")
    parser.add_argument(
        "-c",
        "--config",
        action="store_true",
        help="Show config.yaml and exit.",
    )
    args = parser.parse_args()

    runner = Runner(startup_checker.get_config(), args)
    runner.run()
