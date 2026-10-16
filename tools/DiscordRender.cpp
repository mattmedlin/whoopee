#include "FartVoice.h"
#include <cstdio>
#include <string>
#include <stdexcept>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

// Signed 16-bit little-endian stereo PCM at 48 kHz, for Discord's Opus encoder.
int main(int argc, char** argv)
{
    if (argc != 4) { std::fprintf(stderr, "Usage: whoopee_render pitch duration rasp\n"); return 2; }
    float values[3];
    const float low[] = {-24, 0.08f, 0}, high[] = {24, 3, 1};
    try {
        for (int i=0; i<3; ++i) {
            std::size_t consumed=0;
            values[i]=std::stof(argv[i+1], &consumed);
            if (consumed!=std::string(argv[i+1]).size() || !std::isfinite(values[i])
                || values[i]<low[i] || values[i]>high[i]) throw std::invalid_argument("range");
        }
    } catch (...) { std::fprintf(stderr, "Invalid pitch, duration, or rasp\n"); return 2; }
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    FartVoice voice;
    voice.prepare(48000);
    voice.start(60, 1, values[0], values[1], values[2]);
    for (int frame=0; frame<static_cast<int>(std::lround(48000.0*values[1])); ++frame) {
        const auto sample=static_cast<std::int16_t>(std::lround(std::clamp(voice.next()*0.3548134f, -1.0f, 1.0f)*32767));
        const auto bits=static_cast<std::uint16_t>(sample);
        const unsigned char bytes[]={static_cast<unsigned char>(bits&255), static_cast<unsigned char>(bits>>8),
                                     static_cast<unsigned char>(bits&255), static_cast<unsigned char>(bits>>8)};
        if (std::fwrite(bytes, 1, 4, stdout)!=4) return 1;
    }
    return std::fflush(stdout)==0 ? 0 : 1;
}
