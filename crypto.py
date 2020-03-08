from cryptography.fernet import Fernet, MultiFernet

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import sys
import binascii
import base64

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
    print ("Decripted msg:",m.decode("utf-8"))
    return m

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
    print("device_shared_key", device_shared_key)

    # here we need to recive device public_key
    server_shared_key = server_private_key.exchange(device_private_key.public_key())
    print("server_shared_key",server_shared_key)

# Diffie Hellman
#non_ephemeral_DH()

# Fernet test
print("test encriptacion multi clave ")
m = b"t"
f = multiKeysFernetGenKeys(4)
t = fernetEncrypt(f, m)
t = fernetKeyRotation(f,t)
d = fernetDecrypt(f, t)

print("test encriptacion clave simple")
m = b"test encriptacion clave simple"
f = simpleKeyFernetGenKey()
t = fernetEncrypt(f, m)
d= fernetDecrypt(f, t)




