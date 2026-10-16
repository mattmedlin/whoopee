#include "FartVoice.h"
#include <cstdio>
#include <cstdlib>
// Emit native float32 mono PCM for comparison; optional sample rate and note.
int main(int argc,char** argv)
{
    const double rate=argc>1?std::atof(argv[1]):44100;
    const int note=argc>2?std::atoi(argv[2]):60;
    FartVoice voice;voice.prepare(rate);voice.start(note,1,0,0.8f,0.55f);
    for(int i=0;i<static_cast<int>(rate);++i)
    { const float sample=voice.next();if(std::fwrite(&sample,sizeof sample,1,stdout)!=1)return 1; }
}
