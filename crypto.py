from cryptography.fernet import Fernet, MultiFernet

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from Crypto.Cipher import DES3
from Crypto.Random import get_random_bytes
from Crypto import Random

import os
import binascii

# Fernet is a symmetric encryption method which makes sure that the
# message encrypted cannot be manipulated/read without the key. It 
# uses URL safe encoding for the keys. Fernet uses 128-bit AES in 
# CBC mode and PKCS7 padding, with HMAC using SHA256 for 
# authentication. The IV is created from os.random(). This page 
# decodes the token.

# Fernet (symmetric encryption) with key rotation
def multiKeysFernetGenKeys(keysNumber):
    keys = []
    for i in range(keysNumber):
        #generate fernet keys for encrytp and decrypt data
        keys.append(Fernet(Fernet.generate_key()))

    f = MultiFernet(keys)
    return f

def simpleKeyFernetGenKey():
    #generate fernet keys for encrytp and decrypt data
    f=Fernet(Fernet.generate_key())
    return f

def fernetEncrypt(f, message):
    # encrypt data
    token = f.encrypt(message)
    fernetPrint(token)
    return token

def fernetDecrypt(f, token):
    m = f.decrypt(token)
    print ("Fernet decripted msg:",m.decode("utf-8"))
    return m.decode("utf-8")

# rotate token password
def fernetKeyRotation(f, token):
    rotated = f.rotate(token)
    fernetPrint(rotated)
    return rotated

def fernetPrint(token):
    cipher = binascii.hexlify(bytearray(token))
    print ("\nFernet:\t\t",cipher.decode("utf-8"))
    print ("Version:\t",cipher[0:2].decode("utf-8"))
    print ("Time stamp:\t",cipher[2:18].decode("utf-8"))
    #IV = initialization vector
    print ("IV(Salt):\t",cipher[18:50].decode("utf-8"))
    print ("Cypher:\t\t",cipher[50:-64].decode("utf-8"))
    print ("HMAC:\t\t",cipher[-64:].decode("utf-8"))

def tripleDESGenKey():
    key = DES3.adjust_key_parity(get_random_bytes(24))
    iv = Random.new().read(DES3.block_size)
    return key,iv

def tripleDESEncryption(key, msg, iv):
    cipher = DES3.new(key, DES3.MODE_OFB, iv)
    encryptedMsg = cipher.encrypt(msg)
    print("3DES encripted msg:", binascii.hexlify(bytearray(encryptedMsg)).decode("utf-8"))
    return encryptedMsg

def tripleDESDecryption(key, encryptedMsg, iv):
    cipher_decrypt = DES3.new(key, DES3.MODE_OFB, iv) 
    decryptedMsg = cipher_decrypt.decrypt(encryptedMsg)
    print("3DES decripted msg:", decryptedMsg.decode("utf-8"))
    return decryptedMsg.decode("utf-8")
    
def chacha20GenKey():
    key = os.urandom(32)
    nonce = os.urandom(16)
    algorithm = algorithms.ChaCha20(key, nonce)
    cipher = Cipher(algorithm, mode=None, backend=default_backend())
    return cipher

def chacha20Encrypt(cipher, msg):
    encryptor = cipher.encryptor()
    encryptedMsg = encryptor.update(msg)
    print("Chacha20 encripted msg:",binascii.hexlify(bytearray(encryptedMsg)).decode("utf-8"))
    return encryptedMsg

def chacha20Decrypt(cipher, encryptedMsg):
    decryptor = cipher.decryptor()
    msg = decryptor.update(encryptedMsg)
    print("Chacha20 decripted msg:",msg.decode("utf-8"))
    return msg.decode("utf-8")

# Diffie Hellman 
def non_ephemeral_DH():
    # Generate parameters g and p
    parameters = dh.generate_parameters(generator=5, 
                                    key_size=1024,
                                    backend=default_backend())

    print("g = %d"%parameters.parameter_numbers().g)
    print("p = %d\n"%parameters.parameter_numbers().p)

    # Generate a device private key for use in the exchange.
    device_private_key = parameters.generate_private_key()
    # Generate a device public key for send it to server.
    device_public_key = device_private_key.public_key()

    # Generate a server private key for use in the exchange.
    server_private_key = parameters.generate_private_key()
    # Generate a server public key for use in the exchange.
    server_public_key = server_private_key.public_key()
    
    # here we need to recive server public_key
    device_shared_key = device_private_key.exchange(server_private_key.public_key())
    print("device_shared_key", binascii.hexlify(bytearray(device_shared_key)).decode("utf-8"),"\n")
    
    # here we need to recive device public_key
    server_shared_key = server_private_key.exchange(device_private_key.public_key())
    print("server_shared_key",binascii.hexlify(bytearray(server_shared_key)).decode("utf-8"))
    
""" # chacha20 Test
m = b"test encriptacion chacha20 "
c = chacha20GenKey()
encm = chacha20Encrypt(c, m)
chacha20Decrypt(c, encm) """

""" # 3DES Test
k, iv = tripleDESGenKey()
m = b'Cifrado 3DES'
encm = tripleDESEncryption(k, m, iv)
tripleDESDecryption(k, encm, iv)  """

""" # Fernet test
print("test encriptacion multi clave ")
m = b"test encriptacion multi clave "
f = multiKeysFernetGenKeys(4)
t = fernetEncrypt(f, m)
t = fernetKeyRotation(f,t)
d = fernetDecrypt(f, t)

print("test encriptacion clave simple")
m = b"test encriptacion clave simple"
f = simpleKeyFernetGenKey()
t = fernetEncrypt(f, m)
d= fernetDecrypt(f, t) """

""" #Diffie Hellman test
non_ephemeral_DH() """
