import sys
import os
import json
import threading
import subprocess
import webbrowser
import time

from PyQt6 import QtWidgets, QtCore, QtGui

MEMORY_FILE = "friday_memory.json"

def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            return True
    except Exception:
        return False

class Memory:
    def __init__(self, path=MEMORY_FILE):
        self.path = path
        self.data = load_json(self.path)

    def train(self, question, answer):
        self.data[question] = answer
        return save_json(self.path, self.data)

    def delete(self, question):
        if question in self.data:
            del self.data[question]
            return save_json(self.path, self.data)
        return False

    def answer(self, text):
        t = text.casefold()
        for q, a in self.data.items():
            if q.casefold() == t:
                return a, 1.0
        for q, a in self.data.items():
            ql = q.casefold()
            parts = t.split()
            for p in parts:
                if p and p in ql:
                    return a, 0.45
        return None, 0.0

class SpotifyController:
    def __init__(self):
        try:
            import requests
        except Exception:
            requests = None
        self.requests = requests
        self.client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        self.client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        self.access_token = os.environ.get("SPOTIFY_ACCESS_TOKEN")
        self.refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
        self.use_api = False
        if self.requests is not None and (self.access_token or (self.client_id and self.client_secret)):
            self.use_api = True

    def headers(self):
        tok = self.access_token
        if not tok:
            return {}
        return {"Authorization": "Bearer " + tok}

    def api_search_track(self, query):
        if not self.use_api:
            return None
        try:
            params = {"q": query, "type": "track", "limit": "one"}
            r = self.requests.get("https://api.spotify.com/v1/search", params=params, headers=self.headers(), timeout=8)
            if r.status_code == 401 and self.client_id and self.client_secret and self.refresh_token:
                return None
            if r.status_code // 100 == 2:
                data = r.json()
                items = data.get("tracks", {}).get("items", [])
                return items
        except Exception:
            pass
        return None

    def api_play_uri(self, uri):
        if not self.use_api:
            return False
        try:
            body = {"uris": [uri]} if uri.startswith("spotify:track") else {"context_uri": uri}
            r = self.requests.put("https://api.spotify.com/v1/me/player/play", headers=self.headers(), json=body, timeout=6)
            return r.status_code in (200, 204)
        except Exception:
            return False

    def applescript(self, cmd, arg=None):
        try:
            if cmd == "play":
                subprocess.call(["osascript", "-e", 'tell application "Spotify" to play'])
            elif cmd == "pause":
                subprocess.call(["osascript", "-e", 'tell application "Spotify" to pause'])
            elif cmd == "next":
                subprocess.call(["osascript", "-e", 'tell application "Spotify" to next track'])
            elif cmd == "previous":
                subprocess.call(["osascript", "-e", 'tell application "Spotify" to previous track'])
            elif cmd == "playuri" and arg:
                script = 'tell application "Spotify" to play track "{0}"'.format(arg)
                subprocess.call(["osascript", "-e", script])
            elif cmd == "search" and arg:
                q = arg.replace(" ", "+")
                webbrowser.open("spotify:search:" + q)
            return True
        except Exception:
            return False

    def play_playlist_y(self):
        playlist_uri = "spotify:playlist:y"
        ok = False
        if self.use_api:
            ok = self.api_play_uri(playlist_uri)
        if not ok:
            try:
                webbrowser.open("https://open.spotify.com/playlist/y")
                time.sleep(0.6)
                self.applescript("play")
                ok = True
            except Exception:
                ok = False
        return ok

    def search_and_play(self, query):
        if self.use_api:
            items = self.api_search_track(query)
            if items:
                uri = items[0].get("uri")
                return self.api_play_uri(uri)
        return self.applescript("search", query)

    def play(self):
        return self.applescript("play")

    def pause(self):
        return self.applescript("pause")

    def next(self):
        return self.applescript("next")

    def previous(self):
        return self.applescript("previous")

class Core:
    def __init__(self):
        self.memory = Memory()
        self.spotify = SpotifyController()
        self.commands = self.build_commands()

    def safe_popen(self, cmd):
        try:
            subprocess.Popen(cmd)
            return "ejecutado"
        except Exception as e:
            return "error " + str(e)

    def safe_output(self, cmd):
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8", "ignore")
            return out
        except Exception as e:
            return "error " + str(e)

    def confirm(self, text):
        sys.stdout.write(text + " (si/no): ")
        sys.stdout.flush()
        r = sys.stdin.readline().casefold().rstrip("\n")
        return r == "si" or r == "s"

    def build_commands(self):
        h = os.path.expanduser
        cmds = {}

        apps = [
            ("finder", "Finder"),
            ("safari", "Safari"),
            ("chrome", "Google Chrome"),
            ("spotify", "Spotify"),
            ("terminal", "Terminal"),
            ("notes", "Notes"),
            ("photos", "Photos"),
            ("music", "Music"),
            ("messages", "Messages"),
            ("calendar", "Calendar"),
            ("calculator", "Calculator"),
            ("systemsettings", "System Settings"),
            ("vscode", "Visual Studio Code"),
            ("pycharm", "PyCharm"),
            ("androidstudio", "Android Studio"),
            ("steam", "Steam"),
            ("epic", "Epic Games Launcher"),
            ("roblox", "Roblox"),
            ("minecraft", "Minecraft")
        ]
        for a, name in apps:
            key = "abrir " + a
            cmds[key] = (lambda p, n=name: self.safe_popen(["open", "-a", n]))

        cmds["abrir escritorio"] = (lambda p: self.safe_popen(["open", h("~/Desktop")]))
        cmds["abrir descargas"] = (lambda p: self.safe_popen(["open", h("~/Downloads")]))
        cmds["abrir documentos"] = (lambda p: self.safe_popen(["open", h("~/Documents")]))
        cmds["abrir aplicaciones"] = (lambda p: self.safe_popen(["open", "/Applications"]))

        cmds["listar aplicaciones"] = (lambda p: self.safe_output(["mdfind", "kMDItemKind==Application"]))
        cmds["listar procesos"] = (lambda p: self.safe_output(["ps", "ax"]))
        cmds["uso disco"] = (lambda p: self.safe_output(["df", "-h", "."]))
        cmds["estado bateria"] = (lambda p: self.safe_output(["pmset", "-g", "batt"]))
        cmds["mostrar ip"] = (lambda p: self.safe_output(["bash", "-lc", "ipconfig getifaddr en0 || ipconfig getifaddr en1"]))

        cmds["buscar"] = self.cmd_search
        cmds["abrir url"] = self.cmd_open_url
        cmds["leer archivo"] = self.cmd_read_file
        cmds["crear archivo"] = self.cmd_create_file
        cmds["buscar archivo"] = self.cmd_search_files

        cmds["vaciar papelera"] = (lambda p: (self.safe_popen(["osascript", "-e", 'tell application "Finder" to empty trash']) if self.confirm("Confirmar vaciar la papelera") else "cancelado"))

        cmds["reiniciar finder"] = (lambda p: self.safe_popen(["killall", "Finder"]))
        cmds["reiniciar dock"] = (lambda p: self.safe_popen(["killall", "Dock"]))

        cmds["modo oscuro"] = (lambda p: self.safe_popen(["osascript", "-e", 'tell application "System Events" to tell appearance preferences to set dark mode to true']))
        cmds["modo claro"] = (lambda p: self.safe_popen(["osascript", "-e", 'tell application "System Events" to tell appearance preferences to set dark mode to false']))

        cmds["diagnostico rapido"] = (lambda p: self.safe_output(["top", "-l", "one"]))
        cmds["estado memoria"] = (lambda p: self.safe_output(["vm_stat"]))
        cmds["estado red"] = (lambda p: self.safe_output(["ifconfig"]))

        cmds["reconstruir spotlight"] = (lambda p: (self.safe_popen(["sudo", "mdutil", "-E", "/"]) if self.confirm("Reconstruir Spotlight (requiere sudo)?") else "cancelado"))
        cmds["flush dns"] = (lambda p: (self.safe_popen(["sudo", "dscacheutil", "-flushcache"]) if self.confirm("Flush DNS (requiere sudo)?") else "cancelado"))

        cmds["spotify reproducir playlist y"] = (lambda p: ("ok" if self.spotify.play_playlist_y() else "error spotify"))
        cmds["spotify reproducir"] = (lambda p: ("ok" if self.spotify.play() else "error"))
        cmds["spotify pausar"] = (lambda p: ("ok" if self.spotify.pause() else "error"))
        cmds["spotify siguiente"] = (lambda p: ("ok" if self.spotify.next() else "error"))
        cmds["spotify anterior"] = (lambda p: ("ok" if self.spotify.previous() else "error"))
        cmds["spotify buscar y reproducir"] = (lambda p: self.spotify.search_and_play(p))
        cmds["spotify buscar"] = (lambda p: self.spotify.applescript("search", p) or "abriendo busqueda spotify")

        cmds["apagar sistema"] = (lambda p: (self.safe_popen(["sudo", "shutdown", "-h", "now"]) if self.confirm("Apagar el sistema ahora (requiere sudo)?") else "cancelado"))
        cmds["reiniciar sistema"] = (lambda p: (self.safe_popen(["sudo", "shutdown", "-r", "now"]) if self.confirm("Reiniciar el sistema ahora (requiere sudo)?") else "cancelado"))
        cmds["matar proceso"] = self.cmd_kill_process

        webapps = {
            "youtube": "https://youtube.com",
            "google": "https://google.com",
            "gmail": "https://mail.google.com",
            "github": "https://github.com",
            "maps": "https://maps.google.com",
            "drive": "https://drive.google.com",
            "notion": "https://www.notion.so",
            "wiki": "https://en.wikipedia.org"
        }
        for name, url in webapps.items():
            key = "abrir " + name
            cmds[key] = (lambda p, u=url: (webbrowser.open(u) or "abriendo " + u))

        cmds["comandos"] = (lambda p: "\n".join(sorted(list(cmds.keys()) + list(self.memory.data.keys()))))
        cmds["entrenar"] = self.cmd_train
        cmds["borrar entrenamiento"] = self.cmd_delete_memory
        cmds["mostrar memoria"] = (lambda p: json.dumps(self.memory.data, ensure_ascii=False, indent=2) if self.memory.data else "memoria vacia")
        cmds["salir"] = (lambda p: "exit")

        base_aliases = [
            "abrir instagram", "abrir twitter", "abrir reddit", "abrir tiktok", "abrir linkedin",
            "abrir slack", "abrir telegram", "abrir zoom", "abrir skype", "abrir calendar web",
            "abrir drive web", "abrir classroom", "abrir facebook", "abrir soundcloud", "abrir vimeo",
            "abrir npm", "abrir pypi", "abrir stackoverflow", "abrir docs", "abrir mdn",
            "abrir weather", "abrir news", "abrir finance", "abrir banking", "abrir paypal",
            "abrir photos web", "abrir spotify web", "abrir apple music web", "abrir youtube music",
            "abrir twitch", "abrir blender", "abrir unity hub", "abrir notion desktop", "abrir obsidian",
            "abrir evernote", "abrir microsoft word", "abrir microsoft excel", "abrir powerpoint",
            "abrir keynote", "abrir pages", "abrir numbers", "abrir reminders", "abrir alarms",
            "abrir system preferences", "abrir accessibility", "abrir bluetooth", "abrir wifi settings",
            "abrir time machine", "abrir activity monitor", "abrir disk utility", "abrir terminal iterm",
            "abrir homebrew", "abrir mac app store", "abrir app store", "abrir audio midi setup",
            "abrir migration assistant", "abrir boot camp", "abrir security settings", "abrir privacy settings"
        ]
        for a in base_aliases:
            cmds[a] = (lambda p, a=a: ("alias " + a))

        names = ["tool", "util", "helper", "stark", "arc", "hud", "panel", "core", "engine"]
        verbs = ["open", "show", "list", "status", "check", "start", "stop", "restart"]
        for n in names:
            for v in verbs:
                k = v + " " + n
                cmds[k] = (lambda p, k=k: ("alias " + k))

        return cmds

    def cmd_search(self, text):
        q = (text or "")
        if not q:
            return "indica qué buscar"
        try:
            webbrowser.open("https://www.google.com/search?q=" + q)
            return "buscando " + q
        except Exception as e:
            return "error " + str(e)

    def cmd_open_url(self, text):
        url = (text or "")
        if not url:
            return "indica la url"
        if not url.startswith("http"):
            url = "https://" + url
        try:
            webbrowser.open(url)
            return "abriendo " + url
        except Exception as e:
            return "error " + str(e)

    def cmd_read_file(self, text):
        path = (text or "")
        if not path:
            return "indica la ruta del archivo"
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(8000)
        except Exception as e:
            return "error leyendo archivo " + str(e)

    def cmd_create_file(self, text):
        path = (text or "")
        if not path:
            return "indica la ruta a crear"
        try:
            d = os.path.dirname(path)
            if d and not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return "archivo creado"
        except Exception as e:
            return "error " + str(e)

    def cmd_search_files(self, text):
        term = (text or "")
        if not term:
            return "indica término para buscar"
        try:
            out = subprocess.check_output(["mdfind", term], stderr=subprocess.STDOUT).decode("utf-8", "ignore")
            lines = out.splitlines()
            return "\n".join(lines[:200]) if lines else "no resultados"
        except Exception as e:
            return "error " + str(e)

    def cmd_kill_process(self, text):
        pid = (text or "")
        if not pid:
            return "indica pid"
        if not pid.isdigit():
            return "pid inválido"
        if not self.confirm("Matar proceso " + pid + " ?"):
            return "cancelado"
        try:
            subprocess.check_call(["kill", pid])
            return "proceso terminado"
        except Exception as e:
            return "error " + str(e)

    def cmd_train(self, text):
        parts = (text or "").split("->")
        if len(parts) < 2:
            return "usa formato pregunta -> respuesta"
        q = parts[0].rstrip()
        a = "->".join(parts[1:]).rstrip()
        if not q or not a:
            return "pregunta o respuesta vacia"
        ok = self.memory.train(q, a)
        return "guardado" if ok else "error guardando"

    def cmd_delete_memory(self, text):
        q = (text or "")
        if not q:
            return "indica la pregunta exacta a borrar"
        ok = self.memory.delete(q)
        return "borrado" if ok else "no existe esa entrada"

    def ask(self, text):
        t = (text or "")
        if not t:
            return "escribe un comando"
        lower = t.casefold()
        keys = sorted(list(self.commands.keys()), key=lambda x: -len(x))
        for k in keys:
            if lower.startswith(k):
                param = t[len(k):].lstrip()
                try:
                    res = self.commands[k](param)
                    return res
                except Exception as e:
                    return "error " + str(e)
        ans, conf = self.memory.answer(t)
        if ans is not None:
            return ans
        return "no tengo respuesta. usa entrenar para añadir."

class Worker(QtCore.QObject):
    finished = QtCore.pyqtSignal(str, str)
    def __init__(self, fn, arg):
        super().__init__()
        self.fn = fn
        self.arg = arg
    @QtCore.pyqtSlot()
    def run(self):
        try:
            r = self.fn(self.arg)
            self.finished.emit(self.arg, str(r))
        except Exception as e:
            self.finished.emit(self.arg, "error " + str(e))

class FridayApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.core = Core()
        self.setWindowTitle("Friday — Stark UI")
        self.resize(1100, 700)
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main = QtWidgets.QHBoxLayout(central)
        left = QtWidgets.QVBoxLayout()
        header = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel("FRIDAY")
        self.title.setStyleSheet("color: #7be1ff; font-size: 36pt; font-weight: 800;")
        header.addWidget(self.title)
        header.addStretch()
        btn_cmds = QtWidgets.QPushButton("Comandos")
        btn_cmds.setFixedHeight(36)
        btn_cmds.setStyleSheet("background:#083148;color:#bff4ff;border-radius:6px;padding:6px;")
        btn_cmds.clicked.connect(self.show_commands)
        header.addWidget(btn_cmds)
        btn_train = QtWidgets.QPushButton("Entrenar IA")
        btn_train.setFixedHeight(36)
        btn_train.setStyleSheet("background:#082a3d;color:#bff4ff;border-radius:6px;padding:6px;")
        btn_train.clicked.connect(self.open_train)
        header.addWidget(btn_train)
        left.addLayout(header)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("background:#001116;color:#aef2ff;border:1px solid #08313a;padding:8px;font-family:monospace;")
        left.addWidget(self.output, stretch=1)
        entry_layout = QtWidgets.QHBoxLayout()
        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText("Escribe un comando o pregunta y pulsa Enter")
        self.input.returnPressed.connect(self.on_send)
        self.input.setStyleSheet("background:#021217;color:#cff7ff;padding:8px;border-radius:6px;")
        entry_layout.addWidget(self.input, stretch=1)
        send_btn = QtWidgets.QPushButton("Enviar")
        send_btn.setFixedHeight(36)
        send_btn.setStyleSheet("background:#0b4b63;color:#eaffff;border-radius:6px;")
        send_btn.clicked.connect(self.on_send)
        entry_layout.addWidget(send_btn)
        left.addLayout(entry_layout)
        main.addLayout(left, stretch=3)
        right_frame = QtWidgets.QFrame()
        right_frame.setStyleSheet("background:#03121a;border-left:1px solid #08313a;")
        right_frame.setFixedWidth(300)
        right_layout = QtWidgets.QVBoxLayout(right_frame)
        info_label = QtWidgets.QLabel("Acciones rápidas")
        info_label.setStyleSheet("color:#9fe7ff;font-weight:700;")
        right_layout.addWidget(info_label)
        self.quick = QtWidgets.QListWidget()
        self.quick.setStyleSheet("background:#021319;color:#bdf5ff;")
        quick_items = ["abrir safari", "abrir terminal", "listar aplicaciones", "spotify reproducir", "mostrar ip", "spotify reproducir playlist y"]
        for it in quick_items:
            self.quick.addItem(it)
        right_layout.addWidget(self.quick)
        run_q = QtWidgets.QPushButton("Ejecutar seleccionado")
        run_q.setStyleSheet("background:#083148;color:#bff4ff;border-radius:6px;")
        run_q.clicked.connect(self.run_quick)
        right_layout.addWidget(run_q)
        right_layout.addStretch()
        footer_label = QtWidgets.QLabel("Stark HUD Console")
        footer_label.setStyleSheet("color:#5fe2ff;font-size:10pt;")
        right_layout.addWidget(footer_label)
        main.addWidget(right_frame, stretch=1)
        self._append("Friday: listo. escribe comandos. escribe salir para cerrar.")

    def _append(self, text):
        self.output.appendPlainText(text)

    def on_send(self):
        text = self.input.text()
        if not text:
            return
        self._append("Tu: " + text)
        self.input.clear()
        self._start_worker(self.core.ask, text)

    def _start_worker(self, fn, arg):
        worker = Worker(fn, arg)
        thread = QtCore.QThread()
        worker.moveToThread(thread)
        worker.finished.connect(self._on_finished)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @QtCore.pyqtSlot(str, str)
    def _on_finished(self, cmd, result):
        if result is None:
            result = "sin respuesta"
        if result == "exit":
            self._append("Friday: cerrando")
            QtCore.QCoreApplication.quit()
            return
        self._append("Friday: " + str(result))

    def show_commands(self):
        keys = self.core.commands.keys()
        mem = list(self.core.memory.data.keys())
        all_keys = sorted(list(keys) + mem)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Comandos disponibles")
        dlg.resize(700, 520)
        layout = QtWidgets.QVBoxLayout(dlg)
        txt = QtWidgets.QPlainTextEdit(dlg)
        txt.setReadOnly(True)
        txt.setPlainText("\n".join(all_keys))
        layout.addWidget(txt)
        btn = QtWidgets.QPushButton("Cerrar")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()

    def open_train(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Entrenar Friday")
        dlg.resize(520, 220)
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.addWidget(QtWidgets.QLabel("Pregunta"))
        entq = QtWidgets.QLineEdit(dlg)
        layout.addWidget(entq)
        layout.addWidget(QtWidgets.QLabel("Respuesta"))
        enta = QtWidgets.QLineEdit(dlg)
        layout.addWidget(enta)
        btn_layout = QtWidgets.QHBoxLayout()
        save = QtWidgets.QPushButton("Guardar")
        save.clicked.connect(lambda: self._save_training(entq.text(), enta.text(), dlg))
        cancel = QtWidgets.QPushButton("Cancelar")
        cancel.clicked.connect(dlg.reject)
        btn_layout.addWidget(save)
        btn_layout.addWidget(cancel)
        layout.addLayout(btn_layout)
        dlg.exec()

    def _save_training(self, q, a, dlg):
        if not q or not a:
            QtWidgets.QMessageBox.warning(self, "Friday", "Completa ambos campos")
            return
        ok = self.core.memory.train(q, a)
        if ok:
            QtWidgets.QMessageBox.information(self, "Friday", "Entrenamiento guardado")
            dlg.accept()
        else:
            QtWidgets.QMessageBox.warning(self, "Friday", "Error al guardar")

    def run_quick(self):
        item = self.quick.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "Friday", "Selecciona una acción rápida")
            return
        cmd = item.text()
        self.input.setText(cmd)
        self.on_send()

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = FridayApp()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
