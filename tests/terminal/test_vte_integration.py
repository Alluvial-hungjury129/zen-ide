"""Tests for VTE terminal integration — configure_vte_scrolling."""

from terminal.terminal_scroll import (
    configure_vte_scrolling,
)


class _FakeSetterTerminal:
    def __init__(self):
        self.fallback_calls = []
        self.pixel_calls = []

    def set_enable_fallback_scrolling(self, enabled):
        self.fallback_calls.append(enabled)

    def set_scroll_unit_is_pixels(self, enabled):
        self.pixel_calls.append(enabled)


class _FakePropertyTerminal:
    def __init__(self):
        self.properties = {
            "enable-fallback-scrolling": object(),
            "scroll-unit-is-pixels": object(),
        }
        self.set_calls = []

    def find_property(self, name):
        return self.properties.get(name)

    def set_property(self, name, value):
        self.set_calls.append((name, value))


class _FakeNoopTerminal:
    def find_property(self, name):
        return None


class TestConfigureVteScrolling:
    def test_prefers_native_setters(self):
        terminal = _FakeSetterTerminal()

        configure_vte_scrolling(terminal)

        assert terminal.fallback_calls == [True]
        assert terminal.pixel_calls == [True]

    def test_falls_back_to_properties(self):
        terminal = _FakePropertyTerminal()

        configure_vte_scrolling(terminal)

        assert terminal.set_calls == [
            ("enable-fallback-scrolling", True),
            ("scroll-unit-is-pixels", True),
        ]

    def test_noops_when_feature_missing(self):
        terminal = _FakeNoopTerminal()

        configure_vte_scrolling(terminal)


import os


def _create_custom_bashrc(config_dir):
    """Standalone version of TerminalView._create_custom_bashrc."""
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
HISTIGNORE="${HISTIGNORE:+$HISTIGNORE:}*___BEGIN___COMMAND_OUTPUT_MARKER___*:*PS1=\\"\\";PS2=\\"\\";unset HISTFILE*:*echo TEST_OK:*sleep 30:*clear; printf '\\033[3J'"

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
HISTFILE="$__zen_real_histfile"
PS1='\[\e[36m\]\W\[\e[0m\]\[\e[33m\]$(__zen_git_prompt)\[\e[0m\] \[\e[32m\]$\[\e[0m\] '
HISTSIZE=1000
HISTFILESIZE=2000
HISTCONTROL=ignoreboth:erasedups
shopt -s histappend
history -n "$HISTFILE" 2>/dev/null
set -o history
"""
    try:
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        bashrc_path = os.path.join(config_dir, "bashrc")
        with open(bashrc_path, "w") as f:
            f.write(bashrc_content)
        return bashrc_path
    except Exception:
        return None


class TestCreateCustomBashrc:
    """Test custom bashrc generation."""

    def test_creates_bashrc_file(self, tmp_path):
        """Bashrc file should be created in config dir."""
        config_dir = str(tmp_path / "config")
        path = _create_custom_bashrc(config_dir)
        assert path is not None
        assert os.path.isfile(path)
        assert path.endswith("bashrc")

    def test_bashrc_content(self, tmp_path):
        """Bashrc should contain expected shell configuration."""
        config_dir = str(tmp_path / "config")
        path = _create_custom_bashrc(config_dir)
        content = open(path).read()

        # Check key sections
        assert "TERM=xterm-256color" in content
        assert "HISTFILE" in content
        assert "__zen_real_histfile" in content
        assert "HISTIGNORE=" in content
        assert "set +o history" in content
        assert "set -o history" in content
        assert "awk '" in content
        assert "history -n" in content
        assert "alias gst=" in content
        assert "PROMPT_COMMAND" in content
        assert "printf '\\033]7;file://%s%s\\007'" in content
        assert "printf '\\\\033]7;file://%s%s\\\\007'" not in content
        assert "PS1='\\[\\e[36m\\]\\W" in content
        assert "PS1='\\\\[\\\\e[36m\\\\]\\\\W" not in content
        assert content.rfind("set -o history") > content.rfind("PS1=")

    def test_creates_config_dir(self, tmp_path):
        """Should create config dir if it doesn't exist."""
        config_dir = str(tmp_path / "new" / "config")
        assert not os.path.exists(config_dir)
        path = _create_custom_bashrc(config_dir)
        assert path is not None
        assert os.path.isdir(config_dir)
