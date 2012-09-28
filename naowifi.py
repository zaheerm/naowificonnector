''' NAO Wifi connector
    Copyright (C) 2012 Florian Boucault, Zaheer Merali

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
from naoqi import ALProxy, ALBroker, ALModule
import time
import speller

NAO_IP = "127.0.0.1"


ZaheerNao = None
Speller = None

class NoSuchNetwork(Exception):
    pass

class NoPendingConnection(Exception):
    pass

class NetworkManager(object):
    def list_networks():
        return []

    def connect_to_network(network):
        raise NoSuchNetwork("")

class ALNetworkManager(NetworkManager):
    def __init__(self):
        self.connman = ALProxy("ALConnectionManager", NAO_IP, 9559)
        self.networks = {}
        self.pending_service_id = None

    def list_networks(self):
        self.networks = {}
        self.connman.scan()
        services = self.connman.services()

        for service in services:
            network = dict(service)
            if network["Name"] == "":
                pass
            else:
                self.networks[network["Name"]] = network["ServiceId"]
        return self.networks.keys()

    def connected(self):
        return False
#        state = self.connman.state()
#        print state
#        return state != "offline"

    def connect(self, network_name):
        print "connecting"
        self.pending_service_id = self.networks[network_name]
        try:
            self.connman.connect(self.pending_service_id)
        except Exception as e:
            raise NoSuchNetwork(network_name)

    def forget(self, network_name):
        print "forgetting ", network_name
        service_id = self.networks[network_name]
        try:
            self.connman.forget(service_id)
        except Exception as e:
            print "got exception while forgetting", e
            raise NoSuchNetwork(network_name)

    def set_password(self, password):
        if self.pending_service_id:
            self.connman.setServiceInput([["ServiceId", self.pending_service_id],
                ["Passphrase", password]])
        else:
            raise NoPendingConnection("")

class NaoConnectToNetwork(ALModule):
    def __init__(self, name, spelling):
        self.al = ALNetworkManager()
        self.tts = ALProxy("ALTextToSpeech", NAO_IP, 9559)
        self.memory = ALProxy("ALMemory")
        self.module_name = name
        self.spelling = spelling
        self.connected = False
        ALModule.__init__(self, name)

    @staticmethod
    def int2text(number):
        numbers = { 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine" }
        return numbers.get(number)

    def start(self):
        if self.al.connected():
            self.tts.say("You are already connected")
        else:
            self.networks = self.al.list_networks()
            self.tts.say("Here are the Wi Fi networks")
            for num, network in enumerate(self.networks, 1):
                self.tts.say(network)
                self.tts.say("is number %d" % (num,))
                time.sleep(0.2)
            if len(self.networks) == 0:
                self.tts.say("Sorry you are in a wifi free zone")
            else:
                self.tts.say("Which number Wi Fi network shall I connect to?")
                try:
                    self.memory.unsubscribeToEvent("WordRecognized")
                except Exception:
                    pass
                speech_recognition = ALProxy("ALSpeechRecognition", NAO_IP, 9559)
                speech_recognition.setLanguage("English")
                try:
                    speech_recognition.setWordListAsVocabulary([str(i) for i in range(1, len(self.networks))])
                except Exception:
                    self.tts.say("Could not set vocabulary")
                try:
                    result = self.memory.subscribeToEvent("WordRecognized", self.module_name, "on_word_recognised")
                    print "Subscribed to event WordRecognized with package ", self.module_name, " and result ", result
                except Exception as e:
                    print "Failed to subscribe ", e

    def on_word_recognised(self, _event_name, confidences, _):
        """ called when nao detects a word """
        self.memory.unsubscribeToEvent("WordRecognized", self.module_name)
        most_confident = (None, 0.)
        enumerated_confidences = list(enumerate(confidences))
        for index, possible in enumerated_confidences[::2]:
            if confidences[index+1] > most_confident[1]:
                most_confident = (possible, confidences[index+1])
        if most_confident[1] < 0.5:
            self.memory.subscribeToEvent("WordRecognized", self.module_name, "on_word_recognised")
            return     
        self.chosen_network = self.networks[int(most_confident[0]) - 1]
        self.tts.say("You chose Wi Fi network " + self.chosen_network)
        self.memory.subscribeToEvent("NetworkServiceInputRequired", self.module_name, "on_input_required")
        self.memory.subscribeToEvent("NetworkServiceStateChanged", self.module_name, "on_network_changed")
        print "subscribed to network events"
        #self.chosen_network = "NAO"
        self.al.connect(self.chosen_network)

    def on_network_changed(self, _event_name, state, _subscriber):
        """ called when network state changed """
        service_id, connection_state = state
        if service_id == self.al.pending_service_id:
            if connection_state == "ready":
                self.tts.say("I am now connected and so happy")
                self.memory.unsubscribeToEvent("NetworkServiceStateChanged", self.module_name)
                self.al.pending_service_id = None
                self.connected = True
            elif connection_state == "failure":
                self.tts.say("I am not connected and am sad")
                self.memory.unsubscribeToEvent("NetworkServiceStateChanged", self.module_name)
                if self.chosen_network:
                    self.al.forget(self.chosen_network)
                self.start()

    def on_input_required(self, _event_name, input_request, _subscriber):
        """ called when nao needs network input """
        self.memory.unsubscribeToEvent("NetworkServiceInputRequired", self.module_name)
        self.tts.say("I need a password, please spell it to me")
        self.memory.unsubscribeToEvent("NetworkServiceStateChanged", self.module_name) 
        self.spelling.beginSpelling(self.got_password, additionalStopCommand='connect')

    def got_password(self, password):
        #self.tts.say("I will try to connect with password ")
        #self.spelling.saySpelling(password)
        self.memory.subscribeToEvent("NetworkServiceStateChanged", self.module_name, "on_network_changed")
        self.tts.say("Connecting")
        self.al.set_password(password) #"RoboticOverlords") #password

    def stop(self):
        self.tts.say("You terminated me!")
        try:
            self.memory.unsubscribeToEvent("WordRecognized", self.module_name)
        except Exception as e:
            print "Got exception unsubscribing to event", e
            pass
        
if __name__ == '__main__':
    broker = ALBroker("myBroker",
                "0.0.0.0",   # listen to anyone
                0,           # find a free port and use it
                NAO_IP,      # parent broker IP
                9559)        # parent broker port
    import sys
    if len(sys.argv) > 1:
        NAO_IP = sys.argv[1]
    spelling = speller.SpellerModule("Speller")
    spelling.Speller = spelling
    Speller = spelling
    ZaheerNao = NaoConnectToNetwork("ZaheerNao", spelling)
    try:
        ZaheerNao.start()
        try:
            while True:
                if ZaheerNao.connected:
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    except Exception:
        pass
    finally:
        ZaheerNao.stop()
        broker.shutdown()
