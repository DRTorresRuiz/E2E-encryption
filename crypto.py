from cryptography.fernet import Fernet, MultiFernet

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# Fernet (symmetric encryption) with key rotation
def fernetGenKeys():
    #generate fernet keys for encrytp and decrypt data
    key1 = Fernet(Fernet.generate_key()) 
    key2 = Fernet(Fernet.generate_key())
    key3 = Fernet(Fernet.generate_key())
    
    f = MultiFernet([key1, key2, key3])
    return f

def fernetEncrypt(f, message):
    # encrypt data
    token = f.encrypt(message)
    print("Encripted data:", token)
    return token

def fernetDecrypt(f, token):
    m = f.decrypt(token)
    return m

# rotate token password
def fernetKeyRotation(f, token):
    rotated = f.rotate(token)
    return rotated



m = b"Hola"
f = fernetGenKeys()
t = fernetEncrypt(f, m)
print("token:", t)
print("decryptedMsg", fernetDecrypt(f,t))
t = fernetKeyRotation(f,t)
print("token:", t)
fernetDecrypt(f, t)



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

#non_ephemeral_DH()




