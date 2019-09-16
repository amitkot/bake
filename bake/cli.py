import sys
import click
import json

from .bakefile import Bakefile
from .config import config
from .clint import eng_join

import pygments
import pygments.lexers
import pygments.formatters


SAFE_ENVIRONS = ["HOME", "PATH", "LANG", "LOCALE", "TERM", "VIRTUAL_ENV"]


def indent(line):
    return f'{" " * 4}{line}'


def echo_json(obj):
    _json = json.dumps(obj, indent=2)

    if sys.stdin.isatty():
        _json = pygments.highlight(
            _json, pygments.lexers.JsonLexer(), pygments.formatters.TerminalFormatter()
        )

    click.echo(_json, err=False)


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument(
    "task",
    type=click.STRING,
    default="__LIST_ALL__",
    envvar="BAKE_TASK",
    # required=False,
)
@click.option(
    "--bakefile",
    "-b",
    default="__BAKEFILE__",
    envvar="BAKEFILE_PATH",
    nargs=1,
    type=click.Path(),
    help="The Bakefile to use.",
)
@click.option(
    "--list",
    "-l",
    "_list",
    default=False,
    is_flag=True,
    help="Lists available tasks from Bakefile.",
)
@click.option("--debug", default=False, is_flag=True, hidden=True)
@click.option("--shellcheck", default=False, is_flag=True, hidden=False)
@click.option(
    "--allow",
    default=False,
    nargs=1,
    multiple=True,
    hidden=False,
    help="Whitelist an environment variable for use.",
)
@click.option("--yes", is_flag=True, help="Set medium–security prompts to yes.")
@click.option(
    "--continue",
    "-c",
    "_continue",
    is_flag=True,
    type=click.BOOL,
    help="Fail immediately, if any task fails.",
)
@click.option(
    "--insecure",
    is_flag=True,
    type=click.BOOL,
    help="Use parent shell's environment variables.",
)
@click.argument(
    "arguments",
    nargs=-1,
    type=click.STRING,
    # multiple=True,
    # help="task ARGV argument (can be passed multiple times).",
)
@click.option("--silent", "-s", is_flag=True, type=click.BOOL, help="Reduce output.")
@click.option(
    "--environ-json",
    "-e",
    nargs=1,
    type=click.STRING,
    help="Environment variables, in JSON format.",
)
@click.option(
    "--json",
    "-j",
    "_json",
    is_flag=True,
    type=click.BOOL,
    help="Output in JSON format (stdout).",
)
def entrypoint(
    *,
    task,
    bakefile,
    arguments,
    _list,
    _continue,
    environ_json,
    shellcheck,
    debug,
    silent,
    insecure,
    allow,
    _json,
    yes,
):
    """bake — a strangely familiar Bash task–runner."""

    # Default to list behavior, when no task is provided.
    if _json:
        silent = True

    SAFE_ENVIRONS.extend(allow)

    if task == "__LIST_ALL__":
        _list = True
        task = None

    if bakefile == "__BAKEFILE__":
        bakefile = Bakefile.find(root=".", filename="Bakefile")
    else:
        bakefile = Bakefile(path=bakefile)

    if not insecure:
        for key in bakefile.environ:
            if key not in SAFE_ENVIRONS:
                del bakefile.environ[key]

    if environ_json:
        bakefile.add_environ_json(environ_json)

    if shellcheck:
        pass

    argv = []
    environ = []

    for i, argument in enumerate(arguments[:]):
        if "=" in argument:
            key, value = argument.split("=", 1)
            environ.append((key, value))
        else:
            argv.append(argument)

    if debug:
        click.echo(f" + argv: {argv!r}", err=True)
        click.echo(f" + environ: {environ!r}", err=True)

    for env in environ:
        key, value = env
        if debug:
            click.echo(
                f" + Setting environ: {click.style(key, fg='red')} {click.style('=', fg='white')} {value}.",
                err=True,
            )
        bakefile.add_environ(key, value)

    bakefile.add_args(*argv)

    if _list and not shellcheck:
        __list_json = {"tasks": {}}

        for _task in bakefile.tasks:
            depends_on = bakefile[_task].depends_on(recursive=True)
            if depends_on:
                deps = []
                for dep in depends_on:
                    if dep.is_filter:
                        dep = click.style(str(dep), fg="yellow")
                    deps.append(str(dep))
                deps = f"\n    {click.style('+', fg='yellow', bold=True)} {eng_join(deps)}."
            else:
                deps = ""
            colon = "" if not deps else "…"

            __list_json["tasks"].update(
                {_task: {"depends_on": [str(d) for d in depends_on]}}
            )

            if not silent:
                click.echo(
                    f" {click.style('-', fg='green', bold=True)} {click.style(_task, bold=True)}{colon}{deps}",
                    err=True,
                )

        if _json:
            echo_json(__list_json)

        sys.exit(0)

    if shellcheck:
        __shellcheck_statuses = []
        for _task in bakefile.tasks:
            _task = bakefile[_task]
            c = _task.shellcheck(silent=silent, debug=debug)
            __shellcheck_statuses.append(c.return_code)
            if not c.ok:
                # click.echo(click.style("Shellcheck failed!", fg="red"), err=True)
                if _json:
                    echo_json(json.loads(c.out))

                for report in json.loads(c.out):
                    level = report["level"]
                    code = report["code"]
                    message = report["message"]
                    line = report["line"]
                    column = (report["column"], report["endColumn"])
                    colored_line_n = click.style(
                        str(line).zfill(3), bg="black", fg="cyan", bold=True
                    )
                    colored_task = click.style(str(_task), fg="yellow", bold=True)
                    actual_line = _task.source_lines[line - 1]

                    click.echo(f"In {colored_task} line {line}:", err=True)
                    click.echo(f"{colored_line_n} {actual_line}", err=True)

                    length = column[1] - column[0]
                    if not length:
                        length = len(actual_line)

                    underline = (" " * 4) + (" " * column[0]) + "^" + "-" * (length - 1)
                    underline += f"SC{code}: {message}"
                    underline = click.style(level, fg="magenta") + click.style(
                        underline[len(level) :], fg="red", bold=True
                    )

                    click.echo(underline, err=True)

        sys.exit(max(__shellcheck_statuses))
    if task:
        try:
            task = bakefile[task]
        except KeyError:
            click.echo(click.style(f"Task {task} does not exist!", fg="red"))
            sys.exit(1)

        def execute_task(task, *, silent=False):
            if not silent:
                click.echo(
                    click.style(" + ", fg="white")
                    + click.style(f"Executing {task}", fg="yellow")
                    + click.style(":", fg="white"),
                    err=True,
                )
            return_code = task.execute(yes=yes, silent=silent)

            if not _continue:
                if not return_code == 0:
                    click.echo(f"Task {task} failed!", err=True)
                    sys.exit(return_code)

        tasks = task.depends_on(recursive=True) + [task]
        for task in tasks:
            execute_task(task, next_task=next_task, silent=silent)

        if not silent:
            click.echo(
                click.style(" + ", fg="white")
                + click.style("Done", fg="green")
                + click.style(".", fg="white"),
                err=True,
            )
        sys.exit(0)


if __name__ == "__main__":
    entrypoint()