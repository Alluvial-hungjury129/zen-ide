"""Terminal shell management mixin.

Handles shell spawning, custom bashrc creation, lifecycle management,
and directory navigation.
"""

import os
import shutil

from gi.repository import GLib, Vte

from shared.git_manager import get_git_manager


class TerminalShellMixin:
    """Mixin providing shell spawning, lifecycle, and directory management."""

    def spawn_shell(self):
        """Spawn the shell process."""
        # Build environment with TERM and color support
        from shared.utils import ensure_full_path

        env = ensure_full_path(os.environ.copy())
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["BASH_SILENCE_DEPRECATION_WARNING"] = "1"
        env["PY_COLORS"] = "1"
        env["FORCE_COLOR"] = "1"
        # Enable colors for ls on macOS (CLICOLOR) and GNU ls (LS_COLORS)
        env["CLICOLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"  # Force colors even when output is not a tty
        env["LSCOLORS"] = "gxfxcxdxbxegedabagacad"
        env["LS_COLORS"] = "di=1;36:ln=35:so=32:pi=33:ex=31:bd=34;46:cd=34;43:su=30;41:sg=30;46:tw=30;42:ow=30;43"
        env_list = [f"{k}={v}" for k, v in env.items()]

        # Create custom bashrc with git aliases and prompt
        bashrc_path = self._create_custom_bashrc()

        # Find bash
        bash_path = shutil.which("bash") or "/bin/bash"
        if not os.path.exists(bash_path):
            for path in ["/usr/bin/bash", "/bin/bash", "/usr/local/bin/bash"]:
                if os.path.exists(path):
                    bash_path = path
                    break

        shell_args = [bash_path, "--rcfile", bashrc_path] if bashrc_path else [bash_path]

        # Use spawn_async for VTE 0.64+
        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            self.cwd,
            shell_args,
            env_list,
            GLib.SpawnFlags.DEFAULT,
            None,  # Child setup
            None,  # Child setup data
            -1,  # Timeout
            None,  # Cancellable
            self._on_spawn_callback,  # Callback
        )

    def _create_custom_bashrc(self):
        """Create custom bashrc with git aliases and prompt."""
        bashrc_content = r"""
# Prevent bootstrap commands in this file from being added to history.
set +o history

# Source user's bash profile first
if [ -f ~/.bash_profile ]; then
    . ~/.bash_profile 2>/dev/null
elif [ -f ~/.bashrc ]; then
    . ~/.bashrc 2>/dev/null
fi

# User shell config may re-enable history; force it back off for Zen bootstrap.
set +o history

export TERM=xterm-256color
export COLORTERM=truecolor
export PY_COLORS=1
export FORCE_COLOR=1

stty erase '^?' 2>/dev/null
shopt -s checkwinsize

# During startup bootstrap, keep history detached from persisted file.
__zen_real_histfile=~/.zen_ide/bash_history
HISTFILE=/dev/null
HISTSIZE=1000
HISTFILESIZE=2000
HISTCONTROL=ignoreboth:erasedups
HISTIGNORE="${HISTIGNORE:+$HISTIGNORE:}*___BEGIN___COMMAND_OUTPUT_MARKER___*:*PS1=\"\";PS2=\"\";unset HISTFILE*:*echo TEST_OK:*sleep 30:*clear; printf '\\033[3J'"

# Enable tab completion
if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion 2>/dev/null
elif [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion 2>/dev/null
elif [ -f /usr/local/etc/bash_completion ]; then
    . /usr/local/etc/bash_completion 2>/dev/null
fi

bind 'set show-all-if-ambiguous on' 2>/dev/null
bind 'set completion-ignore-case on' 2>/dev/null
bind '"\\e[A": history-search-backward' 2>/dev/null
bind '"\\e[B": history-search-forward' 2>/dev/null

if ls --color=auto / >/dev/null 2>&1; then
    alias ls='ls --color=auto'
    alias ll='ls -l --color=auto'
else
    alias ls='ls -G'
    alias ll='ls -lG'
fi

alias gst='git status'
alias groh='git reset --hard @{u}'
alias git_prune_branches='git branch | grep -v "^\\*" | grep -v "^  main$" | xargs git branch -D'

# Zen IDE tools (open_pr, etc.)
if [ -d "$__zen_tools_dir" ]; then
    export PATH="$__zen_tools_dir:$PATH"
fi

# Source user custom aliases
if [ -f ~/.zen_ide/aliases ]; then
    . ~/.zen_ide/aliases 2>/dev/null
fi

bind 'set enable-bracketed-paste off' 2>/dev/null

# Git-aware prompt via PS1 command substitution (avoids visual
# side effects during SIGWINCH redraws).
# PROMPT_COMMAND is reserved for non-visual OSC 7 CWD reporting only.
__zen_git_prompt() {
    local branch
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
    if [ -z "$branch" ]; then
        return
    fi
    if [ ${#branch} -gt 18 ]; then
        branch="${branch:0:15}..."
    fi
    if git diff --no-ext-diff --quiet --exit-code 2>/dev/null && git diff --no-ext-diff --cached --quiet --exit-code 2>/dev/null; then
        printf ' (%s)' "$branch"
    else
        printf ' (%s *)' "$branch"
    fi
}

# Report CWD to terminal emulator via OSC 7 (enables Cmd+click on relative file paths)
__zen_osc7() {
    printf '\033]7;file://%s%s\007' "$(hostname)" "$(pwd)"
}
PROMPT_COMMAND="__zen_osc7"

# Persist only user commands (not startup/probe noise)
# Remove known bootstrap/probe noise persisted by older versions.
if [ -f "$__zen_real_histfile" ]; then
    _zen_hist_tmp="${__zen_real_histfile}.tmp.$$"
    if awk '
        /^HISTFILE=~\/\.zen_ide\/bash_history$/ { next }
        /^HISTSIZE=1000$/ { next }
        /^HISTFILESIZE=2000$/ { next }
        /^HISTCONTROL=ignoreboth(:erasedups)?$/ { next }
        /^if \[ -f \/etc\/bash_completion \]; then/ { next }
        /^if ls --color=auto \/ >\/dev\/null 2>&1; then/ { next }
        /^if \[ -f ~\/\.zen_ide\/aliases \]; then/ { next }
        /^bind '\''set show-all-if-ambiguous on'\'' 2>\/dev\/null$/ { next }
        /^bind '\''set completion-ignore-case on'\'' 2>\/dev\/null$/ { next }
        /^bind '\''"\\e\[A": history-search-backward'\'' 2>\/dev\/null$/ { next }
        /^bind '\''"\\e\[B": history-search-forward'\'' 2>\/dev\/null$/ { next }
        /^alias gst='\''git status'\''$/ { next }
        /^alias groh='\''git reset --hard @\{u\}'\''$/ { next }
        /^alias git_prune_branches=/ { next }
        /^bind '\''set enable-bracketed-paste off'\'' 2>\/dev\/null$/ { next }
        /^__zen_git_prompt\(\) \{/ { next }
        /^__zen_osc7\(\) \{/ { next }
        /^PROMPT_COMMAND="__zen_osc7"$/ { next }
        /^PS1=/ { next }
        /^unset __zen_real_histfile$/ { next }
        /^# Enable tab completion$/ { next }
        /^# Source user custom aliases$/ { next }
        index($0, "___BEGIN___COMMAND_OUTPUT_MARKER___") > 0 { next }
        index($0, "PS1=\"\";PS2=\"\";unset HISTFILE") > 0 { next }
        index($0, "echo TEST_OK") > 0 { next }
        index($0, "sleep 30") > 0 { next }
        index($0, "clear; printf '\\''\\033[3J'\\''") > 0 { next }
        { print }
    ' "$__zen_real_histfile" > "$_zen_hist_tmp" 2>/dev/null; then
        mv "$_zen_hist_tmp" "$__zen_real_histfile"
    else
        rm -f "$_zen_hist_tmp"
    fi
fi

PS1='\[\e[36m\]\W\[\e[0m\]\[\e[33m\]$(__zen_git_prompt)\[\e[0m\] \[\e[32m\]$\[\e[0m\] '

HISTFILE="$__zen_real_histfile"
HISTSIZE=1000
HISTFILESIZE=2000
HISTCONTROL=ignoreboth:erasedups
shopt -s histappend
history -n "$HISTFILE" 2>/dev/null
set -o history
"""
        try:
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)
            bashrc_path = os.path.join(self.config_dir, "bashrc")
            # Resolve tools/ directory relative to source tree
            src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            tools_dir = os.path.join(os.path.dirname(src_dir), "tools")
            with open(bashrc_path, "w") as f:
                f.write(f'__zen_tools_dir="{tools_dir}"\n')
                f.write(bashrc_content)
            return bashrc_path
        except Exception:
            return None

    def _on_spawn_callback(self, terminal, pid, error):
        """Callback when shell spawn completes."""
        if error:
            pass
        else:
            self.shell_pid = pid

    def cleanup(self):
        """Stop respawning and clean up terminal resources for shutdown."""
        self._shutting_down = True
        self.stop_shell()

    def _on_child_exited(self, terminal, status):
        """Handle shell exit."""
        if self._shutting_down:
            return
        # Respawn shell
        GLib.timeout_add(100, lambda: self.spawn_shell() or False)

    def stop_shell(self):
        """Stop the shell process and all its children (e.g. git from prompt)."""
        if hasattr(self, "shell_pid") and self.shell_pid:
            import signal

            try:
                os.killpg(os.getpgid(self.shell_pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    os.kill(self.shell_pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    pass

    def change_directory(self, path: str):
        """Change the terminal's working directory."""
        if os.path.isdir(path):
            old_cwd = self.cwd
            self.cwd = path
            if hasattr(self, "shell_pid") and self.shell_pid:
                cmd = f" cd {path!r}\n"
                git = get_git_manager()
                old_repo = git.get_repo_root(old_cwd) if old_cwd else None
                new_repo = git.get_repo_root(path)
                if old_repo != new_repo:
                    # Hide terminal during repo switch to avoid visible cd transition
                    self.terminal.set_opacity(0)
                    self.terminal.feed_child(cmd.encode())
                    GLib.timeout_add(150, self._deferred_clear_and_reveal)
                else:
                    self.terminal.feed_child(cmd.encode())

    def _deferred_clear_and_reveal(self):
        """Clear terminal after cd completes, then reveal."""
        self.clear()
        self.terminal.set_opacity(1)
        return GLib.SOURCE_REMOVE

    def get_cwd(self) -> str:
        """Get current working directory."""
        return self.cwd
