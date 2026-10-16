#pragma once
#include <juce_audio_utils/juce_audio_utils.h>
#include "FartVoice.h"
#include <array>
#include <atomic>

class WhoopeeProcessor final : public juce::AudioProcessor
{
public:
    WhoopeeProcessor();
    void prepareToPlay(double, int) override;
    void releaseResources() override {}
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    bool isBusesLayoutSupported(const BusesLayout&) const override;
    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }
    const juce::String getName() const override { return "Whoopee"; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return false; }
    double getTailLengthSeconds() const override { return 3.0; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return "Default"; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*, int) override;
    void preview() { previewPending.store(true); }
    juce::AudioProcessorValueTreeState parameters;
private:
    void trigger(int, float);
    std::array<FartVoice, 8> voices;
    std::atomic<bool> previewPending { false };
    juce::SmoothedValue<float> outputGain;
    std::atomic<float>* pitch;
    std::atomic<float>* duration;
    std::atomic<float>* rasp;
    std::atomic<float>* volume;
    unsigned int nextVoice = 0;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(WhoopeeProcessor)
};
