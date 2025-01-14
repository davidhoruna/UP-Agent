__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import pysqlite3 as sqlite3
from pathlib import Path
import streamlit as st
import shutil
import os

class PDFDatabase:
    def __init__(self, db_path="pdf_database.db", pdf_storage="stored_pdfs"):
        self.db_path = db_path
        self.pdf_storage = Path(pdf_storage)
        self.pdf_storage.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdfs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,
                    original_name TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @st.cache_resource
    def get_all_pdfs(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT filename, original_name FROM pdfs")
            return cursor.fetchall()

    def store_pdf(self, uploaded_file):
        try:
            # Generate unique filename
            file_path = self.pdf_storage / uploaded_file.name
            
            # Save file to storage
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO pdfs (filename, original_name) VALUES (?, ?)",
                    (uploaded_file.name, uploaded_file.name)
                )
            
            return True, "PDF guardado exitosamente"
        except sqlite3.IntegrityError:
            return False, "Este archivo ya existe en la base de datos"
        except Exception as e:
            return False, f"Error al guardar el PDF: {str(e)}"

    def delete_pdf(self, filename):
        try:
            # Remove from storage
            file_path = self.pdf_storage / filename
            if file_path.exists():
                file_path.unlink()
            
            # Remove from database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM pdfs WHERE filename = ?", (filename,))
            
            return True, "PDF eliminado exitosamente"
        except Exception as e:
            return False, f"Error al eliminar el PDF: {str(e)}"

    def get_pdf_path(self, filename):
        return self.pdf_storage / filename 