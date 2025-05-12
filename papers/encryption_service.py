import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from django.conf import settings

class EncryptionService:


    def __init__(self, encryption_method="AES"):
        self.encryption_method = encryption_method
        self.key = None
        self.iv = None
    
    def generate_key(self):

        if self.encryption_method == "AES":

            self.key = os.urandom(32)

            self.iv = os.urandom(16)

            key_iv_pair = base64.b64encode(self.key + self.iv).decode('utf-8')
            return key_iv_pair
        else:
            raise ValueError(f"Desteklenmeyen şifreleme yöntemi: {self.encryption_method}")
    
    def load_key(self, key_iv_pair):

        if not key_iv_pair:
            raise ValueError("Anahtar boş olamaz")
            

        key_iv_bytes = base64.b64decode(key_iv_pair)
        
        if self.encryption_method == "AES":

            if len(key_iv_bytes) != 48:
                raise ValueError("Geçersiz anahtar formatı")
                
            self.key = key_iv_bytes[:32]
            self.iv = key_iv_bytes[32:48]
        else:
            raise ValueError(f"Desteklenmeyen şifreleme yöntemi: {self.encryption_method}")
    
    def encrypt(self, plaintext):

        if not plaintext:
            return ""
            
        if not self.key or not self.iv:
            raise ValueError("Önce anahtar oluşturmalı veya yüklemelisiniz")
            
        if self.encryption_method == "AES":

            plaintext_bytes = plaintext.encode('utf-8')
            

            padder = padding.PKCS7(algorithms.AES.block_size).padder()
            padded_data = padder.update(plaintext_bytes) + padder.finalize()
            

            cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.iv), backend=default_backend())
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            

            return base64.b64encode(ciphertext).decode('utf-8')
        else:
            raise ValueError(f"Desteklenmeyen şifreleme yöntemi: {self.encryption_method}")
    
    def decrypt(self, ciphertext):

        if not ciphertext:
            return ""
            
        if not self.key or not self.iv:
            raise ValueError("Önce anahtarı yüklemelisiniz")
            
        if self.encryption_method == "AES":

            ciphertext_bytes = base64.b64decode(ciphertext)
            

            cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(ciphertext_bytes) + decryptor.finalize()
            

            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            plaintext_bytes = unpadder.update(padded_plaintext) + unpadder.finalize()
            

            return plaintext_bytes.decode('utf-8')
        else:
            raise ValueError(f"Desteklenmeyen şifreleme yöntemi: {self.encryption_method}") 