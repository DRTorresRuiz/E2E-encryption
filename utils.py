from cryptography.fernet import Fernet, MultiFernet

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from Crypto.Cipher import DES3, ChaCha20_Poly1305
from Crypto.Random import get_random_bytes
from Crypto import Random
from tinyec import registry
import secrets

import os
import binascii
import json
import hmac
import hashlib

from base64 import b64encode, b64decode
from Crypto.Random import get_random_bytes

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

def simpleFernetGenKey():
    #generate fernet keys for encrytp and decrypt data
    key=Fernet.generate_key()
    return key

def fernetEncrypt(key, message):
    f = Fernet(key)
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


# Deprecated alghoritm
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
    
# Chacha20 without authenticator
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

# Chacha20 with Poly1305 authenticator, Authenticated Encryption with Associated Data (AEAD) algorithm.

def chacha20P1305GenKey():    
    key = get_random_bytes(32)
    return key

def chacha20P1305Encrypt(key, msg, header):
    cipher = ChaCha20_Poly1305.new(key=key)
    cipher.update(header)
    ciphertext, tag = cipher.encrypt_and_digest(msg)
    jk = [ 'nonce', 'header', 'ciphertext', 'tag' ]
    jv = [ b64encode(x).decode('utf-8') for x in (cipher.nonce, header, ciphertext, tag) ]
    encData = json.dumps(dict(zip(jk, jv)))
    print("Encripted data", encData)
    return encData

def chacha20P1305Decrypt(key, encData):    
    b64 = json.loads(encData)
    jk = [ 'nonce', 'header', 'ciphertext', 'tag' ]
    jv = {k:b64decode(b64[k]) for k in jk}

    cipher = ChaCha20_Poly1305.new(key=key, nonce=jv['nonce'])
    cipher.update(jv['header'])
    plaintext = cipher.decrypt_and_verify(jv['ciphertext'], jv['tag'])
    print("Chacha20 decripted msg:",plaintext.decode("utf-8"))


# Diffie Hellman 

# HMAC is a message authentication code (MAC).
def dhParameters():
    # Generate parameters g and p
    parameters = dh.generate_parameters(generator=5, 
                                    key_size=1024,
                                    backend=default_backend())

    print("g = %d"%parameters.parameter_numbers().g)
    print("p = %d\n"%parameters.parameter_numbers().p)
    return parameters

def dhGenKeys(parameters):
    private_key = parameters.generate_private_key()
    public_key = private_key.public_key()

    return private_key, public_key

def dhGenSharedKey(private_key, remote_public_key):
    shared_key = private_key.exchange(remote_public_key)
    
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'handshake data',
        backend=default_backend()
    ).derive(shared_key)

    print("derived_key_shared_key", binascii.hexlify(bytearray(derived_key)).decode("utf-8"),"\n")
    return derived_key


# Elliptic Curve Diffie–Hellman 
# The elliptic curve used for the ECDH calculations is 256-bit named curve brainpoolP256r1. The 
# private keys are 256-bit (64 hex digits) and are generated randomly. The public keys will be 
# 257 bits (65 hex digits), due to key compression.
def compress(pubKey):
    return hex(pubKey.x) + hex(pubKey.y % 2)[2:]

curve = registry.get_curve('brainpoolP256r1')

def ecdhGenKeys(curve):
    private_key = secrets.randbelow(curve.field.n)
    public_key = private_key * curve.g
    print("public key:", public_key)
    return private_key, public_key

def ecdhGenSharedKey(private_key, remote_public_key):
    shared_key = private_key * remote_public_key
    shared_key = str.encode(compress(shared_key))

    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'handshake data',
        backend=default_backend()
    ).derive(shared_key) 
    
    print("derived_key_shared_key", binascii.hexlify(bytearray(derived_key)).decode("utf-8"),"\n")
    return derived_key

def get_message( payload, encriptor ):
    """
        Returns the message in JSON format, otherwise an empty string.
        Checks if it is encrypted or not.
    """
    message = ""
    if is_json( payload ):
        # The message received is loaded as a dictionary by using json library.
        message = json.loads( payload )
    else:
        # We try to decypher this message...
        if encriptor != None:
            encrypted_message = payload
            possible_message = encriptor.decrypt( encrypted_message.encode() )
            if is_json( possible_message ):
                # If it is a JSON we continue the process...
                message = json.loads( possible_message.decode( "utf-8" ) )
    return message


def send( client, encriptor, msg ):
    """ 
        This function sends a message to an specified topic.
        Returns True if message was sent correctly, otherwise False. 
        The `msg` need to include the `topic` parameter.
    """
    topic = msg.get( "topic", "" )
    if topic == "":

        print( "The following message couldn't be sent: ", msg )
        return False
    elif encriptor == None:

        #print( "WARNING: Plain message sent. No encription have been applied in the following message: ", msg )
        client.publish( topic, json.dumps( msg ) )
        return False
    else:
        # Cypher the message before sending it.
        message = json.dumps( msg )
        encryptedMessage = encriptor.encrypt( message.encode() )
        client.publish( topic, encryptedMessage.decode( "utf-8" ) )
        return True

""" # Elliptic Curve Diffie Hellman test
# Generate a device private and public keys for use in the exchange.
device_private_key, device_public_key = ecdhGenKeys(curve)
# Generate a device private and public keys for use in the exchange.
server_private_key, server_public_key = ecdhGenKeys(curve)
# Generate a device shared key 
device_shared_key = ecdhGenSharedKey(device_private_key, server_public_key)
# Generate a server shared key
server_shared_key = ecdhGenSharedKey(server_private_key, device_public_key) """


""" #Diffie Hellman test
# Generate parameters g and p
parameters = dhParameters()
# Generate a device private and public keys for use in the exchange.
device_private_key, device_public_key = dhGenKeys(parameters)
# Generate a device private and public keys for use in the exchange.
server_private_key, server_public_key = dhGenKeys(parameters)
# Generate a device shared key 
device_shared_key = dhGenSharedKey(device_private_key, server_public_key)
# Generate a server shared key
server_shared_key = dhGenSharedKey(server_private_key, device_public_key)

header = b"header"
msg = b'Test chacha20Polly1305'
encData = chacha20P1305Encrypt(device_shared_key, msg, header)
chacha20P1305Decrypt(device_shared_key, encData) """


""" string = b"password"
key=b"bill"    
print ("HMAC (MD5):", hmac.new(key, string,hashlib.md5).hexdigest())
print ("HMAC (SHA1):", hmac.new(key, string, hashlib.sha1).hexdigest())
print ("HMAC (SHA224):", hmac.new(key, string, hashlib.sha224).hexdigest())
print ("HMAC (SHA256):", hmac.new(key, string, hashlib.sha256).hexdigest())
print ("HMAC (SHA384):", hmac.new(key, string, hashlib.sha384).hexdigest())
print ("HMAC (SHA512):", hmac.new(key, string, hashlib.sha512).hexdigest()) """


"""  # Test chacha20Polly1305
header = b"header"
msg = b'Test chacha20Polly1305'

key = chacha20P1305GenKey()
encData = chacha20P1305Encrypt(key, msg, header)
chacha20P1305Decrypt(key, encData)   """

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

