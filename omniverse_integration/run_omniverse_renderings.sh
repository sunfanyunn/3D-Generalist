#!/bin/bash -ex

BLENDER_PATH=/home/owner/Downloads/blender-4.2.1-linux-x64/blender
TARGET_DIR=$(pwd)/sample_scenes/a_minimal_living_room
OUTPUT_DIR=/home/owner/Desktop/ORO_output
ADD_ON_PATH=/home/owner/scripts/addons/omni_optimization_panel/batch/optimize_export.py

# $BLENDER_PYTHON_PATH oro_convert.py $TARGET_DIR
#$BLENDER_PATH $TARGET_DIR/scene_topdown.blend --python oro_convert.py $TARGET_DIR $OUTPUT_DIR
#$BLENDER_PATH $TARGET_DIR/scene_topdown.blend --python /home/owner/scripts/addons/omni_optimization_panel/batch/optimize_export.py -- $TARGET_DIR/tmp.usdc
python3 oro_convert.py $TARGET_DIR $OUTPUT_DIR

cd ~/.local/share/ov/pkg/isaac-sim-4.0.0-rc.21
bash isaac-sim.sh --enable omni.replicator.object \
    --/log/file=$TARGET_DIR/omni.replicator.object.log --/log/level=warn --/windowless=True \
    --/config/file=$TARGET_DIR/oro_scene.yaml

#for folder in $(ls evaluation_v1); do
#    cd $CURRENT_DIR
#    BLENDER_PATH=/home/owner/Downloads/blender-4.2.1-linux-x64/blender
#    TARGET_DIR=$CURRENT_DIR/evaluation_v1/$folder/3
#    ADD_ON_PATH=/home/owner/scripts/addons/omni_optimization_panel/batch/optimize_export.py
#
#    # $BLENDER_PYTHON_PATH oro_convert.py $TARGET_DIR
#    #$BLENDER_PATH $TARGET_DIR/scene_topdown.blend --python oro_convert.py $TARGET_DIR $OUTPUT_DIR
#    #$BLENDER_PATH $TARGET_DIR/scene_topdown.blend --python /home/owner/scripts/addons/omni_optimization_panel/batch/optimize_export.py -- $TARGET_DIR/tmp.usdc
#    python3 oro_convert.py $TARGET_DIR $OUTPUT_DIR
#
#    cd /home/owner/.local/share/ov/pkg/isaac-sim-4.0.0-rc.21
#    bash isaac-sim.sh --enable omni.replicator.object \
#        --/log/file=$TARGET_DIR/omni.replicator.object.log --/log/level=warn --/windowless=True \
#        --/config/file=$TARGET_DIR/oro_scene.yaml
#done