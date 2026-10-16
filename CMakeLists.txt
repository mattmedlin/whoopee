cmake_minimum_required(VERSION 3.22)
project(Whoopee VERSION 1.0.0 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
include(CTest)
if(BUILD_TESTING)
    add_executable(dsp_tests Tests/DspTests.cpp)
    target_include_directories(dsp_tests PRIVATE Source)
    add_test(NAME dsp COMMAND dsp_tests)
    add_executable(model_render_raw tools/CalibrateVoice.cpp)
    target_include_directories(model_render_raw PRIVATE Source)
endif()
option(WHOOPEE_BUILD_PLUGIN "Build VST3 and standalone application" ON)
if(NOT WHOOPEE_BUILD_PLUGIN)
    return()
endif()
include(FetchContent)
FetchContent_Declare(JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG 8.0.6
    GIT_SHALLOW TRUE)
FetchContent_MakeAvailable(JUCE)
set(WHOOPEE_FORMATS VST3 Standalone)
if(APPLE)
    list(APPEND WHOOPEE_FORMATS AU)
endif()
juce_add_plugin(Whoopee
    COMPANY_NAME "Whoopee Audio"
    BUNDLE_ID "audio.whoopee.instrument"
    PLUGIN_MANUFACTURER_CODE Whop
    PLUGIN_CODE Frtz
    PRODUCT_NAME "Whoopee"
    IS_SYNTH TRUE
    NEEDS_MIDI_INPUT TRUE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    COPY_PLUGIN_AFTER_BUILD FALSE
    FORMATS ${WHOOPEE_FORMATS})
target_sources(Whoopee PRIVATE Source/PluginProcessor.cpp Source/PluginEditor.cpp)
target_compile_definitions(Whoopee PUBLIC
    JUCE_WEB_BROWSER=0 JUCE_USE_CURL=0 JUCE_VST3_CAN_REPLACE_VST2=0)
target_link_libraries(Whoopee PRIVATE juce::juce_audio_utils
    PUBLIC juce::juce_recommended_config_flags juce::juce_recommended_warning_flags)
if(APPLE)
    foreach(format AU Standalone)
        add_custom_command(TARGET Whoopee_${format} POST_BUILD
            COMMAND /usr/bin/codesign --force --sign - "$<TARGET_BUNDLE_DIR:Whoopee_${format}>")
    endforeach()
endif()
if(BUILD_TESTING)
    add_executable(render_preview Tests/RenderPreview.cpp)
    target_include_directories(render_preview PRIVATE Source)
    target_link_libraries(render_preview PRIVATE Whoopee juce::juce_audio_utils)
    add_test(NAME model_render COMMAND render_preview)
endif()
