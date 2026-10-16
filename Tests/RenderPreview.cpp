#include "PluginProcessor.h"
#include <iostream>
int main()
{
    juce::ScopedJuceInitialiser_GUI init;
    WhoopeeProcessor processor;
    processor.prepareToPlay(44100, 44100);
    juce::AudioBuffer<float> audio(2, 44100);
    juce::MidiBuffer midi;
    midi.addEvent(juce::MidiMessage::noteOn(1, 60, 1.0f), 0);
    processor.processBlock(audio, midi);
    const float rms = audio.getRMSLevel(0, 0, audio.getNumSamples());
    if (!std::isfinite(rms) || rms < 0.001f) { std::cerr << "Physical model did not produce audio\n"; return 1; }
    auto destination = juce::File::getCurrentWorkingDirectory().getChildFile("Whoopee-preview.wav");
    auto stream = destination.createOutputStream();
    if (!stream) return 2;
    stream->setPosition(0); stream->truncate();
    juce::WavAudioFormat format;
    std::unique_ptr<juce::AudioFormatWriter> writer(format.createWriterFor(stream.get(), 44100, 2, 16, {}, 0));
    if (!writer) return 3;
    stream.release();
    if (!writer->writeFromAudioSampleBuffer(audio, 0, audio.getNumSamples())) return 4;
    std::cout << "Physical model rendered; RMS " << rms << '\n';
}
