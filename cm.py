import json
import pathlib
import subprocess
import sys
import tempfile
from operator import itemgetter

import toml
import typer
from jsondb import DuplicateEntryError, jsondb
from rich import print
from rich.console import Console
from rich.style import Style
from rich.table import Table

app = typer.Typer()
db = None
cm_root = pathlib.Path.home() / ".local/cm/"
cm_path = pathlib.Path.home() / ".local/cm/cm.json"


def open_temp_toml_file(template=None):
    if not template:
        template = {"command": "", "tag": "", "description": ""}
    fd, filename = tempfile.mkstemp(suffix=".toml", text=True)
    with open(filename, "w") as file:
        toml.dump(template, file)
    write_status = subprocess.call("$EDITOR {}".format(filename), shell=True)
    return filename, write_status


def insert(command):
    if not command.get("command"):
        print("[red]no command provided")
        sys.exit()
    if not command.get("tag"):
        print("[red]tag is not provided")
        sys.exit()
    if len(command.get("tag")) > 20 or len(command.get("description")) > 30:
        print(
            "[red]Length of tag and description should be less than 20 and 30 characters respectively"
        )
        sys.exit()
    try:
        db.insert([command])
    except DuplicateEntryError as err:
        print("[red]Duplicate entry found - {}".format(command.get("description")))
    print("[green bold]command added")


def get_commands_sorted():
    commands = db.find(lambda x: True)
    return sorted(commands, key=itemgetter("tag"))


def select_command():
    selected = subprocess.Popen(
        "cm ls | sk --ansi --with-nth 2..",
        shell=True,
        stdout=subprocess.PIPE,
    ).communicate()[0]
    if selected:
        lineno = selected.decode("utf-8").split(":")[0].strip()
        return get_commands_sorted()[int(lineno)]["command"]


@app.command()
def ls():
    console = Console(color_system="256")
    sorted_commands = get_commands_sorted()
    table = Table.grid(expand=True)
    table.add_column(no_wrap=True)
    table.add_column(max_width=10, no_wrap=True, style="blue")
    table.add_column(max_width=25, no_wrap=True, style="green")
    table.add_column(max_width=30, no_wrap=True, style="bold")
    for count, entry in enumerate(sorted_commands):
        table.add_row(
            str(count) + ":",
            entry.get("tag"),
            "  " + entry.get("description"),
            "  " + entry.get("command"),
        )
    console.print(table, overflow="ellipsis", soft_wrap=True, end="")


@app.command()
def new():
    filename, status = open_temp_toml_file()
    if status == 0:
        with open(filename, "r") as file:
            command = toml.load(file)
            insert(command)


@app.command()
def add():
    selected = subprocess.Popen(
        "cat ~/.bash_history | sk",
        shell=True,
        stdout=subprocess.PIPE,
    ).communicate()[0]
    if selected:
        command = selected.decode("utf-8").strip()
        filename, _ = open_temp_toml_file(
            {"command": command, "tag": "", "description": ""}
        )
        with open(filename, "r") as file:
            command = toml.load(file)
            insert(command)


@app.command()
def edit():
    command = select_command()

    def update(document):
        if document:
            filename, status = open_temp_toml_file(document)
            if status == 0:
                with open(filename, "r") as file:
                    command = toml.load(file)
                    document.update(command)
                    return document

    db.update(update, lambda x: x.get("command") == command)


@app.command()
def rm():
    command = select_command()
    if command:
        db.delete(lambda x: x.get("command") == command)
        print("[bold green]command deleted")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        command = select_command()
        if command:
            subprocess.run(
                "stty -echo && xdotool type '{}' && stty echo".format(command),
                shell=True,
            )


def run():
    global db
    db = jsondb(str(cm_path))
    db.set_index("command")
    db.set_index("description")
    app()
    cm_root.mkdir(parents=True, exist_ok=True)
