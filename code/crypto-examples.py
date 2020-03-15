
import utils as utils # Include different common fucntions.
import hmac
import hashlib
from cryptography.hazmat.primitives.serialization import PublicFormat, Encoding, load_pem_public_key

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

string = b"password"
key=b"bill"    
print ("HMAC (MD5):", hmac.new(key, string,hashlib.md5).hexdigest())
print ("HMAC (SHA1):", hmac.new(key, string, hashlib.sha1).hexdigest())
print ("HMAC (SHA224):", hmac.new(key, string, hashlib.sha224).hexdigest())
print ("HMAC (SHA256):", hmac.new(key, string, hashlib.sha256).hexdigest())
print ("HMAC (SHA384):", hmac.new(key, string, hashlib.sha384).hexdigest())
print ("HMAC (SHA512):", hmac.new(key, string, hashlib.sha512).hexdigest())

# Fernet test
print("test encriptacion multi clave ")
m = b"test encriptacion multi clave "
f = utils.multiKeysFernetGenKeys(4)
t = utils.fernetEncrypt(f, m)
t = utils.fernetKeyRotation(f,t)
d = utils.fernetDecrypt(f, t)
