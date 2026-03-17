# Test file for nim-command-injection rule

import osproc
import strformat
import strutils

# ruleid: nim-command-injection
let userCmd = "rm -rf /"
discard execShellCmd("ls " & userCmd)

# ruleid: nim-command-injection
discard execShellCmd(fmt"echo {$userCmd}")

# ruleid: nim-command-injection
discard execProcess("git clone " & userCmd)

# ruleid: nim-command-injection
let p = startProcess(&"curl {$userCmd}")

# ruleid: nim-command-injection
discard execShellCmd("cat " & userCmd & " | grep foo")

# ok: nim-command-injection - uses safe args array
discard execProcess("ls", args = [userCmd], options = {poUsePath})

# ok: nim-command-injection - hardcoded string
discard execShellCmd("echo hello")

# ok: nim-command-injection - hardcoded string
discard execProcess("git status")
