# Separating Composite Objects in Objaverse

In Objaverse, many assets are structured as composite objects, meaning they are a combination of multiple distinct elements grouped together into a single asset. To make these assets more usable for simulation or analysis, this code provides a systematic approach to **separate composite objects into individual assets**. For example:

- A sofa with pillows is split into the sofa frame and individual pillows.  
- An asset labeled "many bottles" is separated into individual bottles.

This solution overcomes the limitations of Blender's default **"Separate by Loose Parts"** method, which may fail to preserve entire sub-objects. Instead, a **custom distance-based separation approach** ensures accurate splitting by checking the spatial proximity of vertices. 


## How to Use in Blender

### Step 1: Set Up Your Workspace
1. Open Blender and load the composite object you want to separate.
2. Ensure the object is selected in **Object Mode**.

### Step 2: Run the Script
1. Open the **Scripting** workspace in Blender.
2. Create a new script or paste the code into an existing one.
3. Adjust the `distance_threshold` parameter in the script to control the separation precision.
4. Execute the script by clicking **Run Script**.

### Step 3: Inspect the Results
1. Once the script completes, switch to **Object Mode**.
2. You’ll see the composite object separated into individual assets in the **Outliner** panel.


## Key Features

1. **Group Vertices by Distance Threshold**  
   - Objects are grouped based on a configurable distance threshold to account for closely packed but non-connected vertices.

2. **Iterative Separation**  
   - Each cluster of vertices is processed to create standalone objects, ensuring precise separation of all individual components.

