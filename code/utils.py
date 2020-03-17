from cryptography.hazmat.primitives.serialization import PublicFormat, \
    Encoding, load_pem_public_key
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from chacha20poly1305 import ChaCha20Poly1305 
from Crypto.Random import get_random_bytes
from base64 import b64encode, b64decode
from tinyec import registry
from Crypto import Random
import binascii
import hashlib
import secrets
import json
import hmac
import os

# ECDH Curve from 
# https://cryptobook.nakov.com/asymmetric-key-ciphers/ecdh-key-exchange-examples
curve = registry.get_curve( 'brainpoolP256r1' )

def simpleFernetGenKey():
    """
        Generates fernet keys for encrytp and decrypt data
    """
    key=Fernet.generate_key()
    return key

def fernetPrint( token ):
    """
        Prints Fernet AEAD Data
    """
    cipher = binascii.hexlify( bytearray( token ) )
    print ( "\nFernet:\t\t",cipher.decode( "utf-8" ) )
    print ( "Version:\t",cipher[0:2].decode( "utf-8" ) )
    print ( "Time stamp:\t",cipher[2:18].decode( "utf-8" ) )
    print ( "IV(Salt):\t",cipher[18:50].decode( "utf-8" ) )
    print ( "Cypher:\t\t",cipher[50:-64].decode( "utf-8" ) )
    print ( "HMAC:\t\t",cipher[-64:].decode( "utf-8" ) )

def dhParameters():
    """
        Generates parameters G and P for DH
    """
    parameters = dh.generate_parameters( generator=5, \
        key_size=512, backend=default_backend() )
    return parameters

def dhGenKeys( parameters ):
    """
        Generates private and public key using DH parameters
    """
    private_key = parameters.generate_private_key()
    public_key = private_key.public_key()
    return private_key, public_key

def dhGenSharedKey( private_key, remote_public_key ):
    """
        Returns Derived Shared Key from DH Private 
        and Remote Public key
    """
    shared_key = private_key.exchange( remote_public_key )
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'handshake data',
        backend=default_backend()
    ).derive(shared_key)
    return derived_key

def compress( pubKey ):
    """
        Concatenates public key values with some operation
        and returns a 256 bit key. 
    """
    return hex( pubKey.x ) + hex( pubKey.y % 2 )[2:]

def ecdhGenKeys( curve ):
    """
        Generates ECDH Private and Public Key.
    """ 
    private_key = secrets.randbelow( curve.field.n )
    public_key = private_key * curve.g
    return private_key, public_key

def ecdhGenSharedKey( private_key, remote_public_key ):
    """
        Returns Derived Shared Key from ECDH Private
        and Remote Public Key.
    """
    shared_key = private_key * remote_public_key
    shared_key = str.encode( compress( shared_key ) )
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'handshake data',
        backend=default_backend()
    ).derive( shared_key ) 
    #print( "derived_key_shared_key", \
    # binascii.hexlify( bytearray( derived_key ) ).decode( "utf-8" ), "\n" )
    return derived_key

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

def get_message( payload, encriptor, hash_key ):
    """
        Returns the message in JSON format, otherwise an empty string.
        Checks if it is encrypted or not.
    """
    message = ""
    trustful = True
    if is_json( payload ):
        # The message received is loaded as a dictionary by using json library.
        message = json.loads( payload )
    else:
        # We try to decypher this message...
        if encriptor != None:
            
            encrypted_message = payload
            possible_message = ""
            if isinstance( encriptor, Fernet ):
                
                try:
                    possible_message = encriptor.decrypt( encrypted_message.encode() )
                except InvalidToken:
                    pass
            elif isinstance( encriptor, ChaCha20Poly1305 ):
                
                fixedNonce = b"147235869147"
                try:
                    possible_message = encriptor.decrypt( fixedNonce, \
                        encrypted_message.encode("latin-1") )
                except InvalidToken:
                    pass
            if is_json( possible_message ):
                # If it is a JSON we continue the process...
                message = json.loads( possible_message.decode( "utf-8" ) )
    # Check HMAC for Authentication 
    if message != "":
        
        _id = message.get( "id", "" )
        _topic = message.get( "topic", "" )
        _timestamp = message.get( "timestamp", "" )
        _wrap = message.get( "wrap", "" ) 
        if _id != "" and _topic != "" and _timestamp != "" and _wrap != "":

            header = {
                "id": _id,
                "topic": _topic,
                "timestamp": _timestamp
            }
            sign = hmac.new( hash_key, json.dumps( header ).encode(), \
                hashlib.sha384 ).hexdigest()
            del message["wrap"]
            message["sign"] = sign
            wrap = hmac.new( sign.encode(), json.dumps( message ).encode(), \
                hashlib.sha384 ).hexdigest()
            if _wrap != wrap:
                
                message = ""
                trustful = False
                print( "Not trustful message." )         
    return message, trustful

def send( client, encriptor, msg ):
    """ 
        This function sends a message to an specified topic.
        Returns True if message was sent correctly, otherwise False. 
        The `msg` need to include the `topic` parameter.
        The `msg` need also to include the `sign` parameter.
    """
    sign = msg.get( "sign", "" )
    if sign != "":

        msg["wrap"] = hmac.new( sign.encode(), json.dumps( msg ).encode(), \
            hashlib.sha384 ).hexdigest()
        del msg["sign"]

    topic = msg.get( "topic", "" )
    if topic == "":

        print( "The following message couldn't be sent: ", msg )
        return False
    elif encriptor == None:

        #print( "WARNING: Plain message sent. No encription have \
        # been applied in the following message: ", msg )
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
            client.publish( topic, encryptedMessage.decode( "latin-1" ) )


def send_error( client, topic, error_message ):
    """
        This function sends an `error_message` to 
        the topic specified.
        Returns True if message was sent correctly, otherwise False.
    """
    if topic == "":

        print( "The following error message couldn't be sent to ", \
            topic, ": ", error_message )
        return False
    else:
        # Build and send an error_message
        error = {
            "topic": topic,
            "error": error_message
        }
        print( "ERROR: ", error_message )
        send( topic, None, error )

def is_json( msg ):
    """
        Verify if a string contains a JSON.
        Ref: https://stackoverflow.com/a/11294685
    """
    try:

        json.loads( msg )
    except ValueError:

        return False
    return True

def generate_new_key( symmetricAlgorithm ):
    """
        Generates new key depending on the symmetric
        algorithm used. Fernet and ChaCha20Poly1305 supported.
    """
    if symmetricAlgorithm == "fernet":
                    
        return simpleFernetGenKey().decode( "utf-8" )
    elif symmetricAlgorithm == "chacha":

        return os.urandom(32).decode( "latin-1" )
    return ""

def modify_encriptor( key, symmetricAlgorithm ):
    """
        Returns a new encriptor by using a new key and depending
        on the symmetric algorithm specified. Fernet and ChaCha20Poly1305 supported.
    """
    if symmetricAlgorithm == "fernet":

        return Fernet( key.encode( "utf-8" ) )
    elif symmetricAlgorithm == "chacha":

        return ChaCha20Poly1305( key.encode( "latin-1" ) )
    return None