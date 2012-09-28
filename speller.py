import string
import time
import sys
from naoqi import ALProxy
from naoqi import ALModule
from naoqi import ALBroker

#NAO_IP = "144.82.97.250"
NAO_IP = "localhost"
Speller = None

class SpellerModule(ALModule):

    def __init__(self, name):
        ALModule.__init__(self, name)
        self.name = name
        self.tts = ALProxy("ALTextToSpeech")
        self.asr = ALProxy("ALSpeechRecognition")
        self.memory = ALProxy("ALMemory")
#        self.asr.setLanguage("English")
        self.word = ""
        self.letters = list(string.ascii_lowercase) + list(string.digits)
        self.correctCommands = ["delete", "back"]
        self.stopCommands = ["stop"]
        self.capitalTag = "capital"
        self.capitalLetters = map(lambda l: self.capitalTag + " " + l, self.letters)
        self.capitalMode = False

    def beginSpelling(self, callback=None, additionalStopCommand=None):
        self.word = ""
        self.capitalMode = False
        self.asr.setAudioExpression(False)
        if additionalStopCommand and additionalStopCommand not in self.stopCommands:
            self.stopCommands.append(additionalStopCommand)

        vocabulary = self.letters + \
                     self.correctCommands + \
                     self.stopCommands + \
                     self.capitalLetters

        self.asr.setWordListAsVocabulary(vocabulary)
        self.memory.subscribeToEvent("WordRecognized", self.name, "onWordRecognized")
        self.callback = callback

    def endSpelling(self):
        self.memory.unsubscribeToEvent("WordRecognized", self.name)
        if self.callback:
            self.callback(self.word)

    def sayLetter(self, letter):
        if (self.isUppercase(letter)):
            self.tts.say("capital")
            self.tts.say(letter)
        else:
            self.tts.say(letter)

    def saySpelling(self, word):
        for letter in word:
            self.sayLetter(letter)
            time.sleep(0.1)

    def onWordRecognized(self, eventName, value, subscriberIdentifier):
        recognizedWord = value[0]
        confidence = value[1]
        difference = 9
        print "word: %s confidence: %f" % (recognizedWord, confidence)
        if len(value) > 3:
            difference = confidence - value[3]
            print "difference: %f %f" % (difference, difference - 0.01)
        if (confidence < 0.5 or difference < 0.03):
            return

        if (recognizedWord in self.correctCommands):
            self.capitalMode = False
            deletedLetter = self.word[-1]
            self.word = self.word[:-1]
            self.tts.say("deleted " + deletedLetter)
        elif (recognizedWord in self.stopCommands):
            self.capitalMode = False
            self.endSpelling()
        elif (recognizedWord == self.capitalTag):
            self.capitalMode = True
        else:
            if (self.capitalMode):
                recognizedWord = string.upper(recognizedWord)

            self.word += recognizedWord
            self.capitalMode = False
            self.memory.unsubscribeToEvent("WordRecognized", self.name)
            self.sayLetter(recognizedWord)
            self.memory.subscribeToEvent("WordRecognized", self.name, "onWordRecognized")

    def isUppercase(self, word):
        if word not in string.ascii_letters:
            return False
        else:
            return word.upper() == word

    def stop(self):
        self.tts.say("You terminated me!")
        self.memory.unsubscribeToEvent("WordRecognized", self.name)

def main():
    myBroker = ALBroker("myBroker", "0.0.0.0", 0, NAO_IP, 9559)
    global Speller
    Speller = SpellerModule("Speller")
    Speller.beginSpelling(additionalStopCommand="connect")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        Speller.stop()
        myBroker.shutdown()
        sys.exit(0)

if __name__ == "__main__":
    main()

