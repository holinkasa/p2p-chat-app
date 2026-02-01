import flet as ft
import asyncio
import json
import time
import os

class CryptoManager:
    """Simple encryption manager using available libraries"""
    def __init__(self):
        self.key = os.urandom(32)
        self.peer_key = None
    
    def get_public_key_bytes(self) -> bytes:
        return self.key
    
    def set_peer_key(self, peer_key: bytes):
        self.peer_key = peer_key
    
    def encrypt(self, plaintext: bytes) -> bytes:
        # Simple XOR encryption for demo (use PyNaCl in production)
        if not self.peer_key:
            return plaintext
        key = self.peer_key * (len(plaintext) // len(self.peer_key) + 1)
        return bytes([p ^ k for p, k in zip(plaintext, key[:len(plaintext)])])
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        return self.encrypt(ciphertext)  # XOR is symmetric


class MessageStore:
    """Store messages with optional expiry"""
    def __init__(self):
        self.messages = []
    
    def add(self, sender: str, message: str, ttl: int = None):
        expiry = time.time() + ttl if ttl else None
        self.messages.append({
            "sender": sender,
            "message": message,
            "expiry": expiry,
            "time": time.strftime("%H:%M")
        })
    
    def delete_all(self):
        self.messages.clear()
    
    def cleanup_expired(self):
        now = time.time()
        self.messages = [m for m in self.messages if not m.get("expiry") or m["expiry"] > now]
    
    def get_all(self):
        self.cleanup_expired()
        return self.messages


class P2PChatApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "🔒 P2P Secure Chat"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 10
        self.page.window_width = 400
        self.page.window_height = 700
        
        self.crypto = CryptoManager()
        self.store = MessageStore()
        self.is_connected = False
        self.peer_id = None
        
        self.setup_ui()
        self.page.run_task(self.auto_refresh)
    
    def setup_ui(self):
        # Status bar
        self.status_icon = ft.Icon(ft.icons.LOCK_OPEN, color=ft.colors.RED, size=20)
        self.status_text = ft.Text("Not Connected", size=14, weight=ft.FontWeight.BOLD)
        
        status_bar = ft.Container(
            content=ft.Row([self.status_icon, self.status_text], spacing=10),
            padding=10,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=10,
        )
        
        # Chat display
        self.chat_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=10,
            auto_scroll=True,
        )
        
        chat_container = ft.Container(
            content=self.chat_list,
            bgcolor=ft.colors.BLACK12,
            border_radius=10,
            expand=True,
        )
        
        # Message input
        self.msg_input = ft.TextField(
            hint_text="Type a message...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=4,
            border_radius=20,
            on_submit=self.send_message,
        )
        
        send_btn = ft.IconButton(
            icon=ft.icons.SEND_ROUNDED,
            icon_color=ft.colors.WHITE,
            bgcolor=ft.colors.BLUE,
            on_click=self.send_message,
        )
        
        input_row = ft.Row([self.msg_input, send_btn], spacing=10)
        
        # TTL input
        self.ttl_input = ft.TextField(
            hint_text="Auto-delete seconds (optional)",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=10,
        )
        
        # Action buttons
        self.connect_btn = ft.ElevatedButton(
            "Connect",
            icon=ft.icons.LINK,
            on_click=self.show_connect_dialog,
            bgcolor=ft.colors.GREEN,
            color=ft.colors.WHITE,
        )
        
        wipe_btn = ft.ElevatedButton(
            "Wipe Chat",
            icon=ft.icons.DELETE_FOREVER,
            on_click=self.wipe_chat,
            bgcolor=ft.colors.RED,
            color=ft.colors.WHITE,
        )
        
        action_row = ft.Row(
            [self.connect_btn, wipe_btn],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        )
        
        # My ID display
        my_id = self.crypto.get_public_key_bytes().hex()[:16]
        self.my_id_text = ft.Text(f"My ID: {my_id}", size=12, color=ft.colors.GREY)
        
        # Main layout
        self.page.add(
            status_bar,
            self.my_id_text,
            chat_container,
            ft.Row([ft.Icon(ft.icons.TIMER, size=16), self.ttl_input]),
            input_row,
            action_row,
        )
    
    def show_connect_dialog(self, e):
        peer_input = ft.TextField(
            hint_text="Enter peer's ID",
            autofocus=True,
        )
        
        def close_dialog(e):
            dialog.open = False
            self.page.update()
        
        def connect(e):
            peer_id = peer_input.value.strip()
            if peer_id:
                self.connect_to_peer(peer_id)
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Connect to Peer"),
            content=ft.Column([
                ft.Text("Share your ID with your peer:"),
                ft.Text(self.crypto.get_public_key_bytes().hex()[:16], 
                       selectable=True, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text("Enter peer's ID:"),
                peer_input,
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton("Connect", on_click=connect),
            ],
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def connect_to_peer(self, peer_id: str):
        try:
            peer_key = bytes.fromhex(peer_id.ljust(64, '0'))
            self.crypto.set_peer_key(peer_key)
            self.peer_id = peer_id
            self.is_connected = True
            
            self.status_icon.name = ft.icons.LOCK
            self.status_icon.color = ft.colors.GREEN
            self.status_text.value = f"Connected to {peer_id[:8]}..."
            self.connect_btn.text = "Connected"
            self.connect_btn.bgcolor = ft.colors.GREY
            
            self.store.add("System", f"Connected to peer {peer_id[:8]}...")
            self.refresh_chat()
        except Exception as ex:
            self.store.add("System", f"Connection failed: {ex}")
            self.refresh_chat()
    
    def send_message(self, e):
        msg = self.msg_input.value.strip()
        if not msg:
            return
        
        ttl = None
        if self.ttl_input.value and self.ttl_input.value.strip().isdigit():
            ttl = int(self.ttl_input.value.strip())
        
        self.store.add("You", msg, ttl)
        self.msg_input.value = ""
        self.ttl_input.value = ""
        self.refresh_chat()
    
    def wipe_chat(self, e):
        self.store.delete_all()
        self.store.add("System", "🔥 Chat wiped!")
        self.refresh_chat()
    
    def refresh_chat(self):
        self.chat_list.controls.clear()
        
        for msg in self.store.get_all():
            is_you = msg["sender"] == "You"
            is_system = msg["sender"] == "System"
            
            # Time remaining for expiring messages
            time_info = msg.get("time", "")
            if msg.get("expiry"):
                remaining = int(msg["expiry"] - time.time())
                if remaining > 0:
                    time_info += f" 🔥{remaining}s"
            
            # Choose colors
            if is_system:
                bg_color = ft.colors.AMBER_100
                text_color = ft.colors.BLACK
            elif is_you:
                bg_color = ft.colors.BLUE_400
                text_color = ft.colors.WHITE
            else:
                bg_color = ft.colors.GREEN_400
                text_color = ft.colors.WHITE
            
            bubble = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(msg["sender"], size=11, weight=ft.FontWeight.BOLD, color=text_color),
                        ft.Text(time_info, size=10, color=text_color, opacity=0.7),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(msg["message"], size=14, color=text_color),
                ], spacing=2, tight=True),
                bgcolor=bg_color,
                padding=10,
                border_radius=15,
                margin=ft.margin.only(
                    left=50 if is_you else 0,
                    right=0 if is_you else 50,
                ),
            )
            
            self.chat_list.controls.append(bubble)
        
        self.page.update()
    
    async def auto_refresh(self):
        while True:
            self.refresh_chat()
            await asyncio.sleep(1)


def main(page: ft.Page):
    P2PChatApp(page)


if __name__ == "__main__":
    ft.app(target=main)
