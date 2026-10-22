// geodoc tray — phase-2 shell (uTorrent-Web pattern, no webview): spawns the
// python launcher as a child, sits in the tray with Otwórz/Zakończ, opens the
// DEFAULT browser at the tokenized URL from the lockfile, and kills the whole
// child tree on exit. Deliberately tauri-free: tray-icon + tao + open cover
// the entire pattern at a fraction of the surface.
#![windows_subsystem = "windows"]

use std::fs;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, Command};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tray_icon::menu::{Menu, MenuEvent, MenuItem};
use tray_icon::TrayIconBuilder;

fn root() -> PathBuf {
    // installed layout: {app}\src-tauri\geodoc-tray.exe -> app root is parent
    let exe = std::env::current_exe().expect("exe path");
    exe.parent().unwrap().parent().unwrap().to_path_buf()
}

fn lock_url(root: &PathBuf) -> Option<String> {
    fs::read_to_string(root.join("contexts").join(".shell.lock"))
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| s.starts_with("http"))
}

fn spawn_launcher(root: &PathBuf) -> Option<Child> {
    let pyw = root.join("python-embed").join("pythonw.exe");
    let py = if pyw.is_file() {
        pyw
    } else {
        PathBuf::from("pythonw.exe") // dev layout: system python
    };
    Command::new(py)
        .arg(root.join("start_geodoc.pyw"))
        .current_dir(root)
        .spawn()
        .ok()
}

fn icon() -> tray_icon::Icon {
    // 32x32 programmatic mark: znacznik osnowy (survey point marker) from
    // DESIGN-SYSTEM.md — ink #182430 on a paper #F8FAF5 coin, drawn in code
    // (exe stays asset-free) with 4x supersampling for clean edges
    const S: i32 = 128; // supersample grid; output 32
    let hit = |x: f32, y: f32| -> Option<[u8; 4]> {
        let (cx, cy) = (S as f32 / 2.0, S as f32 / 2.0);
        let d = ((x - cx).powi(2) + (y - cy).powi(2)).sqrt();
        let coin = S as f32 * 0.485;
        if d > coin {
            return None;
        }
        let ink = [24u8, 36, 48, 255];
        let ring_r = S as f32 * 8.5 / 32.0;
        let w = S as f32 * 0.8 / 32.0; // stroke half-width
        let dot = S as f32 * 1.7 / 32.0;
        let tick = (x - cx).abs() <= w && (cy - y).abs() > ring_r
            || (y - cy).abs() <= w && (cx - x).abs() > ring_r;
        let on_ring = (d - ring_r).abs() <= w;
        let in_reach = d <= S as f32 * 13.0 / 32.0;
        if d <= dot || on_ring || (tick && in_reach) {
            Some(ink)
        } else {
            Some([248, 250, 245, 255]) // paper
        }
    };
    let mut rgba = Vec::with_capacity(32 * 32 * 4);
    for oy in 0..32 {
        for ox in 0..32 {
            let (mut r, mut g, mut b, mut a) = (0u32, 0u32, 0u32, 0u32);
            for sy in 0..4 {
                for sx in 0..4 {
                    let x = (ox * 4 + sx) as f32 + 0.5;
                    let y = (oy * 4 + sy) as f32 + 0.5;
                    if let Some(px) = hit(x, y) {
                        r += px[0] as u32;
                        g += px[1] as u32;
                        b += px[2] as u32;
                        a += px[3] as u32;
                    }
                }
            }
            rgba.extend_from_slice(&[(r / 16) as u8, (g / 16) as u8,
                                     (b / 16) as u8, (a / 16) as u8]);
        }
    }
    tray_icon::Icon::from_rgba(rgba, 32, 32).expect("icon")
}

fn main() {
    // AppMutex pairing with the installer (badanie 06.08: Setup/uninstaller
    // refuse to run while this mutex lives) + single-instance guard. Raw
    // kernel32 declaration — the exe stays dependency-free.
    #[link(name = "kernel32")]
    extern "system" {
        fn CreateMutexW(attrs: *const core::ffi::c_void, owner: i32,
                        name: *const u16) -> *mut core::ffi::c_void;
        fn GetLastError() -> u32;
    }
    let mname: Vec<u16> = "geodoc-tray-mutex\0".encode_utf16().collect();
    unsafe {
        CreateMutexW(core::ptr::null(), 0, mname.as_ptr());
        if GetLastError() == 183 {           // ERROR_ALREADY_EXISTS
            let _ = open::that("http://127.0.0.1:7420/");
            return;                          // second instance: just focus UI
        }
    }

    let root = root();
    let mut child = spawn_launcher(&root);

    let menu = Menu::new();
    let open_item = MenuItem::new("Otwórz geodoc", true, None);
    let quit_item = MenuItem::new("Zakończ", true, None);
    let _ = menu.append_items(&[&open_item, &quit_item]);
    let open_id = open_item.id().clone();
    let quit_id = quit_item.id().clone();

    let event_loop = EventLoopBuilder::new().build();
    let _tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip("geodoc — asystent operatów")
        .with_icon(icon())
        .build()
        .expect("tray");

    let menu_rx = MenuEvent::receiver();
    event_loop.run(move |_event, _target, control_flow| {
        *control_flow = ControlFlow::WaitUntil(
            std::time::Instant::now() + std::time::Duration::from_millis(200),
        );
        if let Ok(ev) = menu_rx.try_recv() {
            if ev.id == open_id {
                if let Some(url) = lock_url(&root) {
                    let _ = open::that(url);
                } else {
                    child = child.take().or_else(|| spawn_launcher(&root));
                }
            } else if ev.id == quit_id {
                if let Some(c) = child.take() {
                    // /T reaches the whole tree: launcher -> server -> llama;
                    // Child::kill would orphan everything below the launcher
                    let _ = Command::new("taskkill")
                        .args(["/PID", &c.id().to_string(), "/T", "/F"])
                        .creation_flags(CREATE_NO_WINDOW)
                        .status();
                }
                *control_flow = ControlFlow::Exit;
            }
        }
    });
}
