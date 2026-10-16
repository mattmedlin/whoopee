#include "PluginProcessor.h"
#include "PluginEditor.h"

WhoopeeProcessor::WhoopeeProcessor()
    : AudioProcessor(BusesProperties().withOutput("Output", juce::AudioChannelSet::stereo(), true)),
      parameters(*this, nullptr, "WhoopeeState", {
          std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"pitch", 1}, "Pitch", -24.0f, 24.0f, 0.0f),
          std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"duration", 1}, "Duration", juce::NormalisableRange<float>(0.08f, 3.0f, 0.01f, 0.4f), 0.8f),
          std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"rasp", 1}, "Rasp", 0.0f, 1.0f, 0.55f),
          std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"volume", 1}, "Volume", -48.0f, 0.0f, -9.0f)
      })
{
    pitch = parameters.getRawParameterValue("pitch");
    duration = parameters.getRawParameterValue("duration");
    rasp = parameters.getRawParameterValue("rasp");
    volume = parameters.getRawParameterValue("volume");
}
void WhoopeeProcessor::prepareToPlay(double rate, int)
{
    for (auto& voice : voices) voice.prepare(rate);
    nextVoice = 0;
    previewPending.store(false);
    outputGain.reset(rate, 0.02);
    outputGain.setCurrentAndTargetValue(juce::Decibels::decibelsToGain(volume->load()));
}
bool WhoopeeProcessor::isBusesLayoutSupported(const BusesLayout& layout) const
{
    return layout.getMainInputChannelSet().isDisabled()
        && (layout.getMainOutputChannelSet() == juce::AudioChannelSet::mono()
            || layout.getMainOutputChannelSet() == juce::AudioChannelSet::stereo());
}
void WhoopeeProcessor::trigger(int note, float velocity)
{
    auto* selected = &voices[nextVoice++ % voices.size()];
    for (auto& voice : voices) if (!voice.isActive()) { selected = &voice; break; }
    selected->start(note, velocity, pitch->load(), duration->load(), rasp->load());
}
void WhoopeeProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midi)
{
    juce::ScopedNoDenormals noDenormals;
    buffer.clear();
    outputGain.setTargetValue(juce::Decibels::decibelsToGain(volume->load()));
    const auto liveRasp = rasp->load();
    for (auto& voice : voices) voice.setRasp(liveRasp);
    if (previewPending.exchange(false)) trigger(60, 0.9f);
    auto event = midi.cbegin();
    for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
    {
        while (event != midi.cend() && (*event).samplePosition <= sample)
        {
            const auto message = (*event).getMessage();
            if (message.isNoteOn()) trigger(message.getNoteNumber(), message.getFloatVelocity());
            else if (message.isNoteOff()) for (auto& voice : voices) voice.noteOff(message.getNoteNumber());
            else if (message.isAllSoundOff() || message.isAllNotesOff()) for (auto& voice : voices) voice.stop();
            ++event;
        }
        float value = 0;
        for (auto& voice : voices) value += voice.next();
        value = juce::jlimit(-1.0f, 1.0f, value * outputGain.getNextValue());
        for (int channel = 0; channel < buffer.getNumChannels(); ++channel) buffer.setSample(channel, sample, value);
    }
    midi.clear();
}
juce::AudioProcessorEditor* WhoopeeProcessor::createEditor() { return new WhoopeeEditor(*this); }
void WhoopeeProcessor::getStateInformation(juce::MemoryBlock& dest)
{
    if (auto xml = parameters.copyState().createXml()) copyXmlToBinary(*xml, dest);
}
void WhoopeeProcessor::setStateInformation(const void* data, int size)
{
    if (auto xml = getXmlFromBinary(data, size))
        if (xml->hasTagName(parameters.state.getType())) parameters.replaceState(juce::ValueTree::fromXml(*xml));
}
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new WhoopeeProcessor(); }
