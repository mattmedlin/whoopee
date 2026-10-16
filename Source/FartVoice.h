#pragma once
#include "ReferenceModel.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

// Identified linear physical resonator driven by a fitted contact-force
// trajectory. This is not an autonomous anatomical simulation. No PCM or
// decoder is used at runtime. The stable recurrence represents four damped
// modes; contact forces excite them and a first difference models radiation.
class FartVoice
{
    static constexpr int taps=32, phases=256, banks=4;
    using Table = std::array<std::array<std::array<double,taps>,phases>,banks>;
    static Table makeTable()
    {
        Table table {};
        constexpr double pi=3.14159265358979323846;
        for (size_t b=0;b<banks;++b)
            for (size_t p=0;p<phases;++p)
            {
                const double cutoff=std::pow(0.5,static_cast<double>(b));
                double total=0;
                for (size_t k=0;k<taps;++k)
                {
                    const double distance=static_cast<double>(k)-15-static_cast<double>(p)/phases;
                    const double z=pi*distance*cutoff;
                    const double sinc=std::abs(z)<1e-12 ? 1 : std::sin(z)/z;
                    const double window=0.5+0.5*std::cos(pi*distance/16);
                    table[b][p][k]=cutoff*sinc*window;
                    total+=table[b][p][k];
                }
                for (auto& v:table[b][p]) v/=total;
            }
        return table;
    }
    // Constructed before audio processing; no allocation or table creation
    // occurs in start()/next(). Shared by all voices.
    inline static const Table interpolation=makeTable();
public:
    void prepare(double rate) { sampleRate=std::max(8000.0,rate);stop(); }
    void start(int note,float velocity,float pitch,float duration,float rasp)
    {
        midiNote=note;gain=std::clamp(velocity,0.0f,1.0f);
        const double ratio=std::clamp(std::pow(2.0,(note-60+pitch)/12.0),0.0625,8.0);
        step=whoopee_model::rate*ratio/sampleRate;
        bank=0;while(bank<banks-1 && std::pow(0.5,bank)>1.0/step) ++bank;
        length=std::max(1,static_cast<int>(sampleRate*duration));
        // Spread contact events across the requested duration while leaving
        // each contact pulse and resonator unchanged. Preserve the 0.8 s fit.
        eventStretch=static_cast<double>(duration)*ratio/0.8;
        roughness=std::clamp(rasp,0.0f,1.0f)-0.55f;
        state.fill(0);history.fill(0);position=0;generated=-1;contact=0;age=0;
        release=1;previousForce=0;releasing=false;active=gain>0;
    }
    void noteOff(int note) { if(note==midiNote) releasing=true; }
    void stop() { active=false; }
    bool isActive() const { return active; }
    float next()
    {
        if(!active) return 0;
        const int centre=static_cast<int>(position);
        while(generated<centre+16) generate();
        const int phase=std::clamp(static_cast<int>((position-centre)*phases),0,phases-1);
        double value=0;
        for(int k=0;k<taps;++k)
        {
            const int at=centre+k-15;
            if(at>=0) value+=history[static_cast<unsigned>(at)%history.size()]*interpolation[static_cast<size_t>(bank)][static_cast<size_t>(phase)][static_cast<size_t>(k)];
        }
        if(releasing) release=std::max(0.0f,release-static_cast<float>(1.0/(0.025*sampleRate)));
        const double fade=std::clamp((length-age)/(0.002*sampleRate),0.0,1.0);
        position+=step;
        if(++age>=length || release<=0) active=false;
        return static_cast<float>(std::clamp(value*gain*release*fade,-0.98,0.98));
    }
private:
    int eventTime(const whoopee_model::Contact& event) const
    { return static_cast<int>(std::llround(event.time*eventStretch)); }
    void generate()
    {
        ++generated;
        while(contact<whoopee_model::contacts.size()
              && eventTime(whoopee_model::contacts[contact])+whoopee_model::contacts[contact].width<=generated) ++contact;
        double force=0;
        for(auto i=contact;i<whoopee_model::contacts.size();++i)
        {
            const auto& event=whoopee_model::contacts[i];
            const int start=eventTime(event);
            if(start>generated) break;
            const int elapsed=generated-start;
            if(elapsed<event.width)
                force+=event.force*std::sin(3.14159265358979323846*(elapsed+0.5)/event.width);
        }
        random^=random<<13;random^=random>>17;random^=random<<5;
        force*=1+roughness*(random/2147483648.0-1.0)*1.5;
        const double excitation=force-previousForce;previousForce=force;
        const double value=excitation+state[0];
        for(size_t i=0;i<state.size()-1;++i)
            state[i]=state[i+1]-whoopee_model::denominator[i+1]*value;
        state.back()=-whoopee_model::denominator.back()*value;
        history[static_cast<unsigned>(generated)%history.size()]=value;
    }
    std::array<double,8> state {};
    std::array<double,64> history {};
    double sampleRate=44100,step=1,position=0,previousForce=0,eventStretch=1;
    int generated=-1,length=1,age=0,midiNote=60,bank=0;
    size_t contact=0;
    float gain=0,roughness=0,release=1;
    std::uint32_t random=0x1234abcd;
    bool active=false,releasing=false;
};
