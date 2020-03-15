from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.serialization import PublicFormat, Encoding, load_pem_public_key
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from chacha20poly1305 import ChaCha20Poly1305 
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

# Diffie Hellman 

# HMAC is a message authentication code (MAC).
def dhParameters():
    # Generate parameters g and p
    parameters = dh.generate_parameters(generator=5, 
                                    key_size=512,
                                    backend=default_backend())

    # print("g = %d"%parameters.parameter_numbers().g)
    # print("p = %d\n"%parameters.parameter_numbers().p)
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

    # print("derived_key_shared_key", binascii.hexlify(bytearray(derived_key)).decode("utf-8"),"\n")
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

###################################

def load_key( pubkey ):
    """
        Load public RSA key, with work-around for keys using
        incorrect header/footer format.

        Read more about RSA encryption with cryptography:
        https://cryptography.io/latest/hazmat/primitives/asymmetric/rsa/
    """
    try:

        return load_pem_public_key( pubkey.encode(), default_backend() )
    except ValueError:
        # workaround for https://github.com/travis-ci/travis-api/issues/196
        pubkey = pubkey.replace( 'BEGIN RSA', 'BEGIN' ).replace( 'END RSA', 'END' )
        return load_pem_public_key( pubkey.encode(), default_backend() ) 

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
            possible_message = ""
            if isinstance( encriptor, Fernet ):
                
                possible_message = encriptor.decrypt( encrypted_message.encode() )
            elif isinstance( encriptor, ChaCha20Poly1305 ):
                
                fixedNonce = b"147235869147"
                possible_message = encriptor.decrypt( fixedNonce, encrypted_message.encode("latin-1") )
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
        if isinstance( encriptor, Fernet ):

            encryptedMessage = encriptor.encrypt( message.encode() )
            client.publish( topic, encryptedMessage.decode( "utf-8" ) )
            return True
        elif isinstance( encriptor, ChaCha20Poly1305 ):

            fixedNonce = b"147235869147"
            encryptedMessage = encriptor.encrypt( fixedNonce, message.encode() )
            client.publish( topic, encryptedMessage.decode("latin-1") )


def send_error( client, topic, error_message ):
    """
        This function sends an `error_message` to 
        the topic specified.
        Returns True if message was sent correctly, otherwise False.
    """
    if topic == "":

        print( "The following error message couldn't be sent to ", topic, ": ", error_message )
        return False
    else:

        # Build and send an error_message
        error = {
            "topic": topic,
            "error": error_message
        }
        print( "ERROR: ", error_message )
        send( topic, None, error )

def is_json( x ):
    """
        Verify if a string contains a JSON.
        Ref: https://stackoverflow.com/a/11294685
    """
    try:
        json.loads( x )
    except ValueError:
        return False
    return True
