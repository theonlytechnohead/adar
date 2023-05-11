# Specifications

Here follows the specifications for *adar*, an automated distributed storage system utilising network coding

## Discovery

*adar* is discovered by utilising mDNS or DNS-SD or Bonjour or avahi to allow for a robust, user-friendly mechanism utilising industry standards

| Service property | Value(s) |
| ----- | ----- |
| Name | Device hostname |
| Type | `_adar` |
| Protocol | `_tcp` |
| Server | Device FQDN |
| Port | 6780 |

The service's TXT records must include the following:

| Field | Value |
| ----- | ----- |
| `Description` | `Network coding for automated distributed storage systems` |
| `uuid` | Integer representation of the device's MAC address |

The service's IP addresses must include at least one IPv4 address  
The service's IP addresses should include at least one IPv6 address

## Pairing

The device's MAC address is used to identify peers persistently  
The device's IP address is used to identify peers during connection sessions

Messages contain the UTF-8 representation of text data, and are terminated by a newline character (`\n`)

A pair is initiated by sending `pair?`  
Pairing is accepted by responding with `sure`

Encryption keys are established and stored for the duration of a connection session, using Diffie-Hellman key exchange  
Key exchange is initiated by sending `key?` prefixed to the binary public key of the sender  
The recipient shall respond with `key!` prefixed to their binary public key  
Both parties can now generate a shared key
