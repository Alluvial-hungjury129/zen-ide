/// Zen IDE native launcher — shows a splash window instantly to prevent dock bouncing.
///
/// macOS bounces the dock icon every ~0.8s until the app shows a window.
/// PyInstaller's bootloader takes ~700ms before Python starts, so a Python-level
/// splash window appears too late (~900ms). This native launcher:
/// 1. Shows a minimal dark window within ~50ms (stops bouncing immediately)
/// 2. Execs the real PyInstaller binary which replaces this process
/// 3. The Python runtime hook detects the splash and cleans it up when GTK is ready
///
/// The splash window is passed to the Python process via a shared user defaults key.

import AppKit

// Record launch time for diagnostics
let launchTime = CFAbsoluteTimeGetCurrent()

// Get the path to the real binary (same directory, suffixed with "-bin")
let executablePath = CommandLine.arguments[0]
let executableURL = URL(fileURLWithPath: executablePath)
let directory = executableURL.deletingLastPathComponent().path
let realBinary = directory + "/zen-ide-core"

// Ensure the real binary exists
guard FileManager.default.fileExists(atPath: realBinary) else {
    fputs("Error: \(realBinary) not found\n", stderr)
    exit(1)
}

// Create the application and show splash window
let app = NSApplication.shared
app.setActivationPolicy(.regular)

// Create a minimal dark window matching the IDE's appearance
let screenFrame = NSScreen.main?.frame ?? NSMakeRect(0, 0, 1440, 900)
let windowWidth: CGFloat = 900
let windowHeight: CGFloat = 600
let windowX = (screenFrame.width - windowWidth) / 2
let windowY = (screenFrame.height - windowHeight) / 2

let window = NSWindow(
    contentRect: NSMakeRect(windowX, windowY, windowWidth, windowHeight),
    styleMask: [.titled, .closable, .miniaturizable, .resizable],
    backing: .buffered,
    defer: false
)
window.title = "Zen IDE"
window.backgroundColor = NSColor(red: 0.11, green: 0.11, blue: 0.14, alpha: 1.0)
window.makeKeyAndOrderFront(nil)

// Activate the app (this tells macOS to stop bouncing the dock icon)
if #available(macOS 14.0, *) {
    app.activate()
} else {
    app.activate(ignoringOtherApps: true)
}

let elapsed = (CFAbsoluteTimeGetCurrent() - launchTime) * 1000
fputs("[launcher] Splash shown in \(Int(elapsed))ms\n", stderr)

// Signal to the Python runtime hook that a splash is already showing
setenv("_ZEN_LAUNCHER_SPLASH", "1", 1)
setenv("_ZEN_APPKIT_PRELOADED", "1", 1)

// Exec the real binary (replaces this process, keeping the splash window alive)
// Pass through all original arguments
var args = CommandLine.arguments
args[0] = realBinary
let cArgs = args.map { strdup($0) } + [nil]
execv(realBinary, cArgs)

// If exec fails, print error
fputs("Error: failed to exec \(realBinary): \(String(cString: strerror(errno)))\n", stderr)
exit(1)
