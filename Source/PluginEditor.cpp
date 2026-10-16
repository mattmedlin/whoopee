#include "PluginEditor.h"

WhoopeeEditor::WhoopeeEditor(WhoopeeProcessor& engine) : AudioProcessorEditor(engine)
{
    const std::array<juce::String, 4> ids { "pitch", "duration", "rasp", "volume" };
    const std::array<juce::String, 4> names { "PITCH", "DURATION", "RASP", "VOLUME" };
    const std::array<juce::String, 4> units { " st", " s", "", " dB" };
    for (size_t i = 0; i < knobs.size(); ++i)
    {
        auto& knob = knobs[i];
        knob.setSliderStyle(juce::Slider::RotaryHorizontalVerticalDrag);
        knob.setTextBoxStyle(juce::Slider::TextBoxBelow, false, 100, 24);
        knob.setTextValueSuffix(units[i]);
        knob.setNumDecimalPlacesToDisplay(2);
        knob.setColour(juce::Slider::rotarySliderFillColourId, juce::Colour(0xffc9f060));
        knob.setColour(juce::Slider::textBoxTextColourId, juce::Colours::white);
        knob.setColour(juce::Slider::textBoxOutlineColourId, juce::Colours::transparentBlack);
        knob.setName(names[i]);
        addAndMakeVisible(knob);
        labels[i].setText(names[i], juce::dontSendNotification);
        labels[i].setJustificationType(juce::Justification::centred);
        labels[i].setColour(juce::Label::textColourId, juce::Colour(0xffc0c6b8));
        addAndMakeVisible(labels[i]);
        attachments[i] = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(engine.parameters, ids[i], knob);
    }
    trigger.setColour(juce::TextButton::buttonColourId, juce::Colour(0xffc9f060));
    trigger.setColour(juce::TextButton::textColourOffId, juce::Colour(0xff182116));
    trigger.onClick = [&engine] { engine.preview(); };
    addAndMakeVisible(trigger);
    setSize(600, 360);
}
void WhoopeeEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xff182116));
    g.setColour(juce::Colour(0xffc9f060));
    g.setFont(juce::FontOptions(40.0f, juce::Font::bold));
    g.drawText("WHOOPEE", 24, 18, 552, 54, juce::Justification::centred);
    g.setFont(juce::FontOptions(14.0f));
    g.setColour(juce::Colour(0xffc0c6b8));
    g.drawText("Pressure. Airflow. Questionable acoustics.", 24, 76, 552, 24, juce::Justification::centred);
    g.drawText("Play MIDI notes or press LET IT RIP. Physically modeled airflow.", 16, 323, 568, 22, juce::Justification::centred);
}
void WhoopeeEditor::resized()
{
    for (size_t i = 0; i < knobs.size(); ++i)
    {
        const int x = 24 + static_cast<int>(i) * 140;
        labels[i].setBounds(x, 115, 132, 24);
        knobs[i].setBounds(x, 140, 132, 116);
    }
    trigger.setBounds(180, 273, 240, 40);
}
