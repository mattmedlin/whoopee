#pragma once
#include "PluginProcessor.h"

class WhoopeeEditor final : public juce::AudioProcessorEditor
{
public:
    explicit WhoopeeEditor(WhoopeeProcessor&);
    void paint(juce::Graphics&) override;
    void resized() override;
private:
    juce::TextButton trigger { "LET IT RIP" };
    std::array<juce::Slider, 4> knobs;
    std::array<juce::Label, 4> labels;
    std::array<std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment>, 4> attachments;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(WhoopeeEditor)
};
