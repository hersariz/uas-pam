import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.garden.graph import Graph, MeshLinePlot
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
import sqlite3
import sounddevice as sd
import numpy as np
import time
import os
from kivy.utils import platform
from hover_behavior import HoverBehavior

kivy.require('1.11.1')

class HoverButton(Button, HoverBehavior):
    def __init__(self, **kwargs):
        super(HoverButton, self).__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = [1, 1, 1, 1]  # Warna default
        self.color = [0, 0, 0, 1]  # Warna teks hitam
        self.size_hint = (None, None)
        self.size = (200, 50)  # Ukuran tombol diperlebar

        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[20])
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_enter(self):
        self.background_color = [0, 0, 1, 1]  # Warna biru saat hover

    def on_leave(self):
        self.background_color = [1, 1, 1, 1]  # Warna default

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=[0, 0, 0, 20])  # Tambahkan padding bawah
        self.label = Label(text="Tingkat Kebisingan: 0 dB")
        self.layout.add_widget(self.label)
        
        self.graph = Graph(xlabel='Waktu', ylabel='dB', x_ticks_minor=5, x_ticks_major=25, y_ticks_major=10,
                           y_grid_label=True, x_grid_label=True, padding=5, x_grid=True, y_grid=True, xmin=0, xmax=100, ymin=0, ymax=100)
        self.plot = MeshLinePlot(color=[1, 0, 0, 1])
        self.graph.add_plot(self.plot)
        self.layout.add_widget(self.graph)
        
        self.db_init()
        
        # Layout untuk tombol
        self.button_layout = BoxLayout(size_hint=(None, None), size=(400, 50), pos_hint={'center_x': 0.5}, spacing=10)
        
        # Tombol untuk menyimpan data secara manual
        self.save_button = HoverButton(text="Simpan Data Manual")
        self.save_button.bind(on_press=self.save_data_manually)
        self.button_layout.add_widget(self.save_button)
        
        # Tombol untuk menampilkan file yang telah direkam
        self.record_button = HoverButton(text="Record")
        self.record_button.bind(on_press=self.show_recorded_files)
        self.button_layout.add_widget(self.record_button)
        
        self.layout.add_widget(self.button_layout)
        
        Clock.schedule_interval(self.update, 1.0 / 10.0)
        
        Window.bind(on_mouse_scroll=self.on_mouse_scroll)
        
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO])
        
        self.add_widget(self.layout)

    def db_init(self):
        self.conn = sqlite3.connect('sound_meter.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS sound_data (timestamp TEXT, intensity REAL)''')
        self.conn.commit()

    def update(self, dt):
        volume = self.get_volume()
        self.label.text = f"Tingkat Kebisingan: {volume:.2f} dB"
        
        # Update plot points
        current_time = time.time()
        self.plot.points.append((current_time, volume))
        
        # Keep only the last 100 points
        if len(self.plot.points) > 100:
            self.plot.points = self.plot.points[-100:]
        
        self.graph.xmax = current_time
        self.graph.xmin = current_time - 100
        
        self.save_to_db(volume)

    def get_volume(self):
        duration = 1  # detik
        fs = 44100  # sample rate
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float64')
        sd.wait()
        volume_norm = np.linalg.norm(recording) * 10
        return volume_norm

    def save_to_db(self, volume):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute("INSERT INTO sound_data (timestamp, intensity) VALUES (?, ?)", (timestamp, volume))
        self.conn.commit()

    def save_data_manually(self, instance):
        volume = self.get_volume()
        self.save_to_db(volume)
        self.label.text = f"Data disimpan: {volume:.2f} dB"

    def show_recorded_files(self, instance):
        self.manager.current = 'recorded_files'

    def on_mouse_scroll(self, window, pos, scroll_x, scroll_y):
        zoom_factor = 1.1
        if scroll_y > 0:  # Zoom in
            self.graph.xmin /= zoom_factor
            self.graph.xmax /= zoom_factor
            self.graph.ymin /= zoom_factor
            self.graph.ymax /= zoom_factor
        elif scroll_y < 0:  # Zoom out
            self.graph.xmin *= zoom_factor
            self.graph.xmax *= zoom_factor
            self.graph.ymin *= zoom_factor
            self.graph.ymax *= zoom_factor

        # Pastikan rentang sumbu tidak negatif
        if self.graph.xmin < 0:
            self.graph.xmin = 0
        if self.graph.ymin < 0:
            self.graph.ymin = 0

class RecordedFilesScreen(Screen):
    def __init__(self, **kwargs):
        super(RecordedFilesScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=[10, 10, 10, 10])
        self.label = Label(text="File yang telah direkam:")
        self.layout.add_widget(self.label)
        
        self.file_list = Label(text="")
        self.layout.add_widget(self.file_list)
        
        self.back_button = HoverButton(text="Kembali")
        self.back_button.bind(on_press=self.go_back)
        self.layout.add_widget(self.back_button)
        
        self.add_widget(self.layout)
        
        self.update_file_list()

    def update_file_list(self):
        recorded_files = os.listdir('.')
        recorded_files = [f for f in recorded_files if f.endswith('.wav')]
        self.file_list.text = "\n".join(recorded_files)

    def go_back(self, instance):
        self.manager.current = 'main'

class SoundMeterApp(App):
    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(MainScreen(name='main'))
        self.sm.add_widget(RecordedFilesScreen(name='recorded_files'))
        return self.sm

if __name__ == '__main__':
    SoundMeterApp().run()
