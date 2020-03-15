
import utils as utils # Include different common fucntions.
import hmac
import hashlib

# Elliptic Curve Diffie Hellman test
# Generate a device private and public keys for use in the exchange.
device_private_key, device_public_key = utils.ecdhGenKeys(utils.curve)
# Generate a device private and public keys for use in the exchange.
server_private_key, server_public_key = utils.ecdhGenKeys(utils.curve)
# Generate a device shared key 
device_shared_key = utils.ecdhGenSharedKey(device_private_key, server_public_key)
# Generate a server shared key
server_shared_key = utils.ecdhGenSharedKey(server_private_key, device_public_key)

#Diffie Hellman test
# Generate parameters g and p
parameters = utils.dhParameters()
# Generate a device private and public keys for use in the exchange.
device_private_key, device_public_key = utils.dhGenKeys(parameters)
# Generate a device private and public keys for use in the exchange.
server_private_key, server_public_key = utils.dhGenKeys(parameters)
# Generate a device shared key 
device_shared_key = utils.dhGenSharedKey(device_private_key, server_public_key)
# Generate a server shared key
server_shared_key = utils.dhGenSharedKey(server_private_key, device_public_key)

header = b"header"
msg = b'Test chacha20Polly1305'
encData = utils.chacha20P1305Encrypt(device_shared_key, msg, header)
utils.chacha20P1305Decrypt(device_shared_key, encData)

string = b"password"
key=b"bill"    
print ("HMAC (MD5):", hmac.new(key, string,hashlib.md5).hexdigest())
print ("HMAC (SHA1):", hmac.new(key, string, hashlib.sha1).hexdigest())
print ("HMAC (SHA224):", hmac.new(key, string, hashlib.sha224).hexdigest())
print ("HMAC (SHA256):", hmac.new(key, string, hashlib.sha256).hexdigest())
print ("HMAC (SHA384):", hmac.new(key, string, hashlib.sha384).hexdigest())
print ("HMAC (SHA512):", hmac.new(key, string, hashlib.sha512).hexdigest())

# Test chacha20Polly1305
header = b"header"
msg = b'Test chacha20Polly1305'

key = utils.chacha20P1305GenKey()
encData = utils.chacha20P1305Encrypt(key, msg, header)
utils.chacha20P1305Decrypt(key, encData)   

# chacha20 Test
m = b"test encriptacion chacha20 "
c = utils.chacha20GenKey()
encm = utils.chacha20Encrypt(c, m)
utils.chacha20Decrypt(c, encm)

# 3DES Test
k, iv = utils.tripleDESGenKey()
m = b'Cifrado 3DES'
encm = utils.tripleDESEncryption(k, m, iv)
utils.tripleDESDecryption(k, encm, iv)

# Fernet test
print("test encriptacion multi clave ")
m = b"test encriptacion multi clave "
f = utils.multiKeysFernetGenKeys(4)
t = utils.fernetEncrypt(f, m)
t = utils.fernetKeyRotation(f,t)
d = utils.fernetDecrypt(f, t)

print("test encriptacion clave simple")
m = b"test encriptacion clave simple"
f = utils.simpleKeyFernetGenKey()
t = utils.fernetEncrypt(f, m)
d= utils.fernetDecrypt(f, t)

