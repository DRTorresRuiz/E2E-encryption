# E2E-encryption

> **Authors:**
>
> - Vadim Miron
> - Fernando Gallego Donoso
> - Daniel R. Torres Ruiz

This repository has been created for *Educational Purposes* - project for the **Security and privacy in Application Environments** subject at [the University of Malaga](https://www.uma.es/)

The `code` folder contains the code for the platform ( CLI and Web Platform ), the Key Management System (**KMS**), and IoT devices separated in folders with descriptive names (`platform`, `kms`, and `device`).

These are the task we are going into during this project:

- [ ] **CLI for Devices**:
  - [x] *Authentication and Registration algorithms* used to connect to the platform via MQTT:
    - [x] Algorithm to connect an IoT Device without Input nor Output - only the Internet connection as output, and sensor values as inputs.
    - [x] Algorithm to connect an IoT Device with Input - such as a keyboard.
    - [x] Algorithm to connect an IoT Device with Output - a kind of display.
  - [ ] *Supported Crypto Algorithms*:
    - [ ] *Symmetric*. To send data to the platform via public MQTT topics:
      - [ ] Fernet Simple Keys
      - [ ] Chacha20 with Poly1305 authenticator
    - [ ] *Asymmetric*. To cypher the keys in the Key Exchange Algorithms:
      - [x] DH.
      - [ ] HMAC DH.
      - [ ] ECDH.
      - [ ] Ephemeral Keys.
- [ ] **KMS**:
  - [x] *Register a device into KMS*.
  - [ ] *Key Rotation*. Send keys to device according to the specified symmetric algorithm:
    - [ ] Simple key algorithms
  - [ ] Provide the current key for a device.
  - [ ] Provide the current key for all devices.
- [ ] **Platform**:
  - [ ] *CLI*:
    - [x] Register new device:
      - [x] DH.
      - [ ] HMAC DH.
      - [ ] ECDH.
      - [ ] Ephemeral Keys.
    - [x] List devices / Topics.
    - [x] Remove devices.
    - [ ] Subscribe and read from an specific topic:
      - [x] Subscribe to an specific topic.
      - [ ] Read data from this selected topic. Support symmetric algorithms of encryption:
        - [ ] Fernet Simple Keys
        - [ ] Chacha20 with Poly1305 authenticator
    - [ ] Subscribe and read from all topics at the same time:
      - [x] Subscribe to all topics listed.
      - [ ] Read data from all topics. Support symmetric algorithms of encryption:
        - [ ] Fernet Simple Keys
        - [ ] Chacha20 with Poly1305 authenticator
  - [ ] *Web service*:
    - [ ] Register new device.
    - [ ] List devices / topics.
    - [ ] Remove devices.
    - [ ] Subscribe and read from an specific topic.
    - [ ] Subscribe and read from all topics at the same time.

## Running our code

First of all, we strongly recommend to create a Virtual Environment to work with this project in `Python 3.7.3`. In order to do this, you should run the following commands:

```bash
cd E2E-encryption # Root path of the project
python3 -m venv env
```

If you are working with Visual Studio Code and you create a virtual environment by using its integrated terminal console, it will automatically ask you to activate the environment. If not, run this command from the root path of the project:

```bash
source env/bin/activate

# Once you finish, run:
deactivate
```

Then, you need to install the required Python libraries included in the`requirements.txt` file.

```bash
pip install -r requirements.txt
```

### Devices

```bash
python code/device/device.py connect -u <DEVICE_ID> # A prompt will appear to introduce the password. Alternatively, include `-p <DEVICE_PASSWORD>`
```

### KMS

```bash
python code/kms/server.py connect -u <KMS_ID> # A prompt will appear to introduce the password. Alternatively, include `-p <KMS_PASSWORD>`
```

### Platform

#### CLI

To register a device run:

```bash
python code/platform/cli/e2e.py register -u <PLATFORM_ID> # A prompt will appear to introduce the password. Alternatively, include `-p <PLATFORM_PASSWORD>`
```

This command will listen all topics included in the `registeredDevices.json` file:

```bash
python code/platform/cli/e2e.py connect -u <PLATFORM_ID> # A prompt will appear to introduce the password
```

#### Web Service

```bash
python code/platform/web/manage.py runserver
```
