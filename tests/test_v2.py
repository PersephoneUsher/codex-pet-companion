import json
import math
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from codex_pet_companion.core.atlas import atlas_version, look_direction
from codex_pet_companion.core.constants import STATES
from codex_pet_companion.core.pet_pack import import_pet_pack, export_pet_pack
from codex_pet_companion.core.pets import load_pet_from_folder, discover_pets
from codex_pet_companion.ui_qt.sprites import SpriteFrames, pil_to_pixmap
from codex_pet_companion.ui_qt.app import CompanionController


APP = QApplication.instance() or QApplication([])


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def pet(self, version=2, declared="auto"):
        folder = self.root / f"source{version}"
        folder.mkdir(exist_ok=True)
        atlas = Image.new("RGBA", (1536, 2288 if version == 2 else 1872))
        for row in range(11 if version == 2 else 9):
            for col in range(8):
                atlas.paste((row * 20, col * 30, 100, 255), (col * 192, row * 208, (col + 1) * 192, (row + 1) * 208))
        atlas.save(folder / "spritesheet.png")
        manifest = dict(id="test-pet", displayName="Test", spritesheetPath="spritesheet.png")
        if declared != "missing":
            manifest["spriteVersionNumber"] = version if declared == "auto" else declared
        (folder / "pet.json").write_text(json.dumps(manifest), encoding="utf-8")
        return folder

    def test_geometry_and_strict_versions(self):
        for version, size in ((1, (1536, 1872)), (2, (1536, 2288))):
            self.assertEqual(atlas_version(size), version)
            self.assertEqual(atlas_version(size, version), version)
            with self.assertRaises(ValueError):
                atlas_version(size, 3 - version)
        for invalid in (True, False, 1.0, "2", 0, 3):
            with self.assertRaises(ValueError):
                atlas_version((1536, 2288), invalid)
        with self.assertRaises(ValueError):
            atlas_version((1536, 2000))

    def test_missing_version_inferred_and_bad_manifest_rejected(self):
        for version in (1, 2):
            pet = load_pet_from_folder(self.pet(version, "missing"), "test")
            self.assertEqual(pet.sprite_version, version)
        for invalid in (None, "2", True, 1, 3):
            self.assertIsNone(load_pet_from_folder(self.pet(2, invalid), "test"))
        folder = self.pet()
        (folder / "pet.json").write_text("[]")
        self.assertIsNone(load_pet_from_folder(folder, "test"))

    def test_import_and_discovery_both_versions(self):
        for version in (1, 2):
            folder = self.pet(version)
            pack = self.root / "pet.zip"
            export_pet_pack(folder, "nested", pack)
            self.assertEqual(import_pet_pack(pack, self.root / "data"), "test-pet")
            with patch("codex_pet_companion.core.pets.data_dir", return_value=self.root / "data"):
                pets = [p for p in discover_pets() if p.id == "test-pet"]
            self.assertEqual(pets[0].sprite_version, version)

    def test_invalid_import_preserves_existing_pet(self):
        pack = self.root / "pet.zip"
        export_pet_pack(self.pet(), "nested", pack)
        import_pet_pack(pack, self.root / "data")
        sheet = self.root / "data/pets/test-pet/spritesheet.png"
        original = sheet.read_bytes()
        export_pet_pack(self.pet(2, 1), "nested", pack)
        with self.assertRaises(ValueError):
            import_pet_pack(pack, self.root / "data")
        self.assertEqual(sheet.read_bytes(), original)

    def test_unsafe_paths_rejected(self):
        pack = self.root / "unsafe.zip"
        with zipfile.ZipFile(pack, "w") as z:
            z.writestr("pet.json", json.dumps(dict(id="../outside")))
        with self.assertRaises(ValueError):
            import_pet_pack(pack, self.root / "data")
        with zipfile.ZipFile(pack, "w") as z:
            z.writestr("pet.json", json.dumps(dict(id="safe")))
            z.writestr("../outside", "bad")
        with self.assertRaises(ValueError):
            import_pet_pack(pack, self.root / "data")
        self.assertFalse((self.root / "outside").exists())

    def test_all_sixteen_directions_and_boundaries(self):
        for index in range(16):
            angle = math.radians(index * 22.5)
            self.assertEqual(look_direction(100 * math.sin(angle), -100 * math.cos(angle)), index)
        self.assertIsNone(look_direction(0, 0))
        self.assertIsNone(look_direction(500, 0))
        a = math.radians(12)
        self.assertEqual(look_direction(100*math.sin(a), -100*math.cos(a), 0), 0)
        a = math.radians(15)
        self.assertEqual(look_direction(100*math.sin(a), -100*math.cos(a), 0), 1)
        self.assertEqual(look_direction(-1, -100, 0), 0)

    def test_pixel_exact_standard_and_look_frames(self):
        for version in (1, 2):
            frames = SpriteFrames(self.pet(version) / "spritesheet.png", 1, version)
            self.assertEqual(set(frames.frames), set(STATES))
            for name, (row, durations) in STATES.items():
                self.assertEqual(len(frames.frames[name]), len(durations))
                for col in range(len(durations)):
                    self.assertEqual(frames.get(name, col).toImage().pixelColor(0, 0).getRgb(), (row*20, col*30, 100, 255))
            self.assertEqual(len(frames.look_frames), 16 if version == 2 else 0)
            if version == 2:
                for i in range(16):
                    self.assertEqual(frames.get_look(i).toImage().pixelColor(0, 0).getRgb(), ((9+i//8)*20, (i%8)*30, 100, 255))

    def test_pointer_overlay_preserves_activity_and_drag(self):
        frames = SpriteFrames(self.pet() / "spritesheet.png", 1, 2)
        c = CompanionController.__new__(CompanionController)
        c.look_indices = {}
        c.anim_name, c.frame_index = "idle", 2
        c.compact_dragging = False
        c.state = dict(hunger=100, mood=100, energy=100)
        widget = QLabel()
        widget.resize(192, 208)
        widget.show()
        self.addCleanup(widget.close)
        APP.processEvents()
        center = widget.mapToGlobal(widget.rect().center())
        with patch("codex_pet_companion.ui_qt.app.QCursor.pos", return_value=center + QPoint(100, 0)):
            self.assertEqual(c.pointer_pixmap(frames, widget, "test").cacheKey(), frames.get_look(4).cacheKey())
            self.assertEqual((c.anim_name, c.frame_index), ("idle", 2))
            for status in ("running", "review", "error", "waiting"):
                c.state.update(codex_status=status, codex_status_until=10**12)
                c.pointer_pixmap(frames, widget, "test")
                self.assertIsNone(c.look_indices["test"])
            c.state.clear()
            c.state.update(hunger=100, mood=100, energy=100, current_event="waving", event_until=10**12)
            c.pointer_pixmap(frames, widget, "test")
            self.assertIsNone(c.look_indices["test"])

            c.compact_dragging, c.compact_drag_animation = True, "running-left"
            self.assertEqual(c.current_animation(), "running-left")
            c.pointer_pixmap(frames, widget, "test")
            self.assertIsNone(c.look_indices["test"])

    def test_full_controller_startup_with_detected_codex(self):
        pet = load_pet_from_folder(self.pet(), "test")
        from codex_pet_companion.core.config import DEFAULT_CONFIG
        config = dict(DEFAULT_CONFIG, selectedPetId=pet.id, checkUpdatesOnStartup=False)
        with patch("codex_pet_companion.ui_qt.app.load_config", return_value=config), \
             patch("codex_pet_companion.ui_qt.app.resolve_state_dir", return_value=self.root), \
             patch("codex_pet_companion.ui_qt.app.discover_pets", return_value=[pet]), \
             patch("codex_pet_companion.ui_qt.app.CodexBridge") as bridge:
            bridge.return_value.active_codex_home = self.root / "codex"
            c = CompanionController(APP)
            try:
                c.full.show()
                APP.processEvents()
                c.refresh()
                c.refresh_pointer()
                self.assertIn("Active:", c.codex_source_label())
                self.assertEqual(len(c.full_frames.look_frames), 16)
                QTest.mouseClick(c.full.pet, Qt.MouseButton.LeftButton)
                self.assertEqual(c.state["current_event"], "waving")
                c.begin_compact_drag()
                c.update_compact_drag_direction(-5)
                self.assertEqual(c.anim_name, "running-left")
                c.end_compact_drag()
            finally:
                c.timer.stop()
                c.pointer_timer.stop()
                c.full.hide()
                c.compact.hide()

    def test_mini_window_mouse_events(self):
        from unittest.mock import Mock
        from codex_pet_companion.ui_qt.app import MiniSpriteWindow
        controller = Mock()
        widget = MiniSpriteWindow(controller)
        self.addCleanup(widget.close)
        widget.move(100, 100)
        press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(10, 10), QPointF(110, 110),
                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.mousePressEvent(press)
        controller.begin_compact_drag.assert_called_once()
        move = QMouseEvent(QEvent.Type.MouseMove, QPointF(10, 10), QPointF(170, 140),
                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.mouseMoveEvent(move)
        self.assertEqual(widget.pos(), QPoint(160, 130))
        controller.update_compact_drag_direction.assert_called_once_with(60)
        widget.mouseReleaseEvent(press)
        self.assertIsNone(widget.drag_pos)
        controller.end_compact_drag.assert_called_once()
        widget.mouseDoubleClickEvent(press)
        controller.show_full.assert_called_once()

    @unittest.skipUnless(os.environ.get("PET_TEST_FOLDER"), "Set PET_TEST_FOLDER for a private real-pet integration test")
    def test_real_pet_import_and_frames(self):
        folder = Path(os.environ["PET_TEST_FOLDER"])
        pet = load_pet_from_folder(folder, "real")
        self.assertIsNotNone(pet)
        self.assertEqual(pet.sprite_version, 2)
        pack = self.root / "real.zip"
        export_pet_pack(folder, pet.id, pack)
        import_pet_pack(pack, self.root / "data")
        imported = load_pet_from_folder(self.root / "data/pets" / pet.id, "imported")
        self.assertEqual(imported.spritesheet_path.read_bytes(), pet.spritesheet_path.read_bytes())
        frames = SpriteFrames(imported.spritesheet_path, 1, 2)
        with Image.open(pet.spritesheet_path) as image:
            for i, pixmap in enumerate(frames.look_frames):
                expected = image.convert("RGBA").crop((i%8*192, (9+i//8)*208, (i%8+1)*192, (10+i//8)*208))
                self.assertEqual(pixmap.toImage(), pil_to_pixmap(expected).toImage())


if __name__ == "__main__":
    unittest.main()
