#include "FartVoice.h"
#include <cstdlib>
#include <iostream>


void require(bool condition, const char* message)
{
    if (!condition) { std::cerr << message << '\n'; std::exit(1); }
}
int main()
{
    for (double rate : {22050.0, 44100.0, 48000.0, 96000.0})
        for (int note : {0, 60, 127})
            for (float rasp : {0.0f, 0.5f, 1.0f})
            {
                FartVoice voice;
                voice.prepare(rate);
                require(voice.next() == 0, "Idle voice must be silent");
                voice.start(note, 1, 24, 0.08f, rasp);
                double energy = 0;
                for (int i = 0; i < static_cast<int>(rate * 0.1); ++i)
                {
                    float sample = voice.next();
                    require(std::isfinite(sample) && std::abs(sample) < 1, "Invalid audio sample");
                    energy += sample * sample;
                }
                require(energy > 0.001, "Triggered voice must produce audio");
                require(!voice.isActive() && voice.next() == 0, "Voice must finish");
                voice.start(note, 0, 0, 1, rasp);
                for (int i = 0; i < 100; ++i) require(voice.next() == 0, "Zero velocity must be silent");
                voice.start(note, 1, -24, 3, rasp);
                voice.noteOff(note);
                for (int i = 0; i < static_cast<int>(rate * 0.03); ++i) voice.next();
                require(!voice.isActive(), "Note-off must release within 30 ms");
                voice.start(note, 1, 0, 3, rasp);
                for (int i = 0; i < static_cast<int>(rate * 3.1); ++i)
                {
                    const auto sample = voice.next();
                    require(std::isfinite(sample) && std::abs(sample) <= 1, "Long voice unstable");
                }
                require(!voice.isActive(), "Long voice must finish");
                voice.stop();
                require(voice.next() == 0, "Panic must silence voice");
            }
    // Duration must produce sound beyond the old 0.8-second source end,
    // at different pitches as well as different output rates.
    for (double rate : {44100.0, 48000.0})
        for (int note : {48, 60, 72})
            for (float duration : {0.2f, 0.8f, 1.6f, 3.0f})
            {
                FartVoice voice;
                voice.prepare(rate);
                voice.start(note, 1, 0, duration, 0.55f);
                double lateEnergy = 0;
                const int count = static_cast<int>(rate * duration);
                for (int i = 0; i < count; ++i)
                {
                    const auto sample = voice.next();
                    if (i > count / 2 && i < count * 4 / 5) lateEnergy += sample * sample;
                }
                require(lateEnergy > 0.001, "Duration must sustain audible contact events into its latter half");
                require(!voice.isActive() && voice.next() == 0, "Duration must stop at the requested time");
            }
    for (double rate : {44100.0, 48000.0, 96000.0})
    {
        FartVoice smooth, reference, rough, automated;
        for (auto* v : {&smooth, &reference, &rough, &automated}) v->prepare(rate);
        smooth.start(60, 1, 0, 0.8f, 0);
        reference.start(60, 1, 0, 0.8f, 0.55f);
        rough.start(60, 1, 0, 0.8f, 1);
        automated.start(60, 1, 0, 0.8f, 0);
        double energy=0, lowDifference=0, highDifference=0, automationDifference=0;
        for (int i=0; i<static_cast<int>(rate*0.8); ++i)
        {
            if (i==static_cast<int>(rate*0.2)) automated.setRasp(1);
            const double a=smooth.next(), b=reference.next(), c=rough.next(), d=automated.next();
            energy+=b*b; lowDifference+=(a-b)*(a-b); highDifference+=(c-b)*(c-b);
            if (i>rate*0.3 && i<rate*0.6) automationDifference+=(d-a)*(d-a);
        }
        require(lowDifference>energy*0.15, "Low rasp must noticeably change the reference tone");
        require(highDifference>energy*0.15, "High rasp must noticeably change the reference tone");
        require(automationDifference>energy*0.1, "Rasp changes must affect already-playing notes");
    }
    std::cout << "DSP checks passed at four sample rates across pitch and rasp extremes.\n";
}
