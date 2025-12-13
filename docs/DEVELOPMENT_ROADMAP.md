# Juniper Canopy Fixes and Enhancements

## Next Steps and Development Roadmap

### Fixes and Enhancements for each Juniper Canopy Information Section and Tab

#### Top Status Bar

- Fix: The status bar at the top of the screen is not properly displaying/updating some fields.
  - The "Status" field appears to never be updating. It is always showing "Stopped" through all stages of the training process.
  - The "Phase" field is not updating correctly. It is always showing "Idle" through all stages of the training process.
  - The "Epoch" and "Hidden Units" fields are displaying and updating properly.

#### Training Controls Section

1. Fix: Buttons in the Training Controls section are not resetting after being pressed.
   - After a button is pressed, it stays in "pressed" state and never returns to "unpressed" state.
   - After the first press, these buttons are no longer clickable.
   - This bug applies to all 5 buttons.

2. Fix: The adjustable meta-parameters are not being applied to training after they have been changed.
   - The meta-parameters should be applied to training after they have been changed, but the update should be manual rather than automatic.
     - These training meta-parameters are adjustable with up and down arrows and by entering a value directly.
     - In-progress updates to these fields should not cause numerous changes to the training process while being adjusted.
     - Add a button to manually apply the updated meta-parameters to training as they exist at that moment.

#### Training Metrics Tab

1. Fix: The Candidate Node detailed information section of the Training Metrics tab is not displaying correctly.
   - This candidate data section should always be visible, but it's only visible intermittently.
   - This section should be collapsible into its heading.
   - This candidate information area should retain data from previous, completed candidate pools.
     - Previous candidate pool data should be collapsed into its sub-heading.
     - The current candidate pool data should be added, with its own sub-heading, between the section heading and the previous, collapsed candidate pool data.
     - The list of previous candidate pools should grow downward as new candidate pools are completed.
     - The list of candidate pools should be sorted by recency, with the most recent pool's data at the top.

2. Fix: Range selection in Graphs is not persisting
   - When a range is selected on the Training graphs, the graph zooms in properly to only display that range.
   - However, the display of the selected range resets in ~1 second.
   - This behavior affects both Training graphs:
     - The Training Loss Over Time
     - The Training Accuracy Over Time
   - The manually selected range should persist until a reset button or corresponding reset key, (e.g., Esc) is pressed.

3. Feat: Add replay functionality.
   - Add a button to the Training Metrics tab that allows the user to replay the training process.
     - The replay button should be visible and properly colored in both "light mode" and "dark mode".
     - The replay button should be located in the top right corner of the Training Metrics tab.
     - The replay button should be labeled "Replay".
     - The replay button should be disabled when the training process is running.
     - The replay button should be enabled when:
        - The training process is Paused
        - The training process is Stopped
        - The training process is Completed
        - The training process is Failed
     - For the replay button to begin a replay, the user must have selected a starting point or playback range.
       - The user can select a starting point by clicking on any point in either of the training metrics graphs.
         - Training Loss Over Time graph
         - Training Accuracy Over Time graph
       - The user can select a playback range by clicking and dragging on either of the training metrics graphs.
         - Training Loss Over Time graph
         - Training Accuracy Over Time graph
       - If the user has not selected a starting point or playback range when the replay button is clicked, the user should be prompted to select one.
     - The replay functionality should allow various replay speeds:
       - Step through the training process one iteration at a time.
       - Replay at normal speed.
       - Fast forward - 2X to play through the entire process at a faster speed.
       - Fast forward - 4X to play through the entire process at an even faster speed.
       - Fast forward - 8X to play through the entire process at the fastest speed.

4. Feat: Add Save and Load buttons to the Training Metrics tab.
   - The Save and Load buttons should be visible and properly colored in both "light mode" and "dark mode".
   - The Save and Load buttons should be located near the top right corner of the Training Metrics tab.
   - The Save and Load buttons should be disabled when the training process is running.
   - The Save and Load buttons should be enabled when the training process is Paused, Stopped, Completed, or Failed.
   - Save functionality should write the current state of the training process to a file.
     - The saved file should include, but not be limited to:
       - Current training metrics data
       - Current model parameters
       - Current training meta-parameters
     - The user should be prompted to select a file location and name when the Save button is clicked.
     - The default file name should include the current date and time.
     - The file should be saved in a format that can be easily loaded and replayed by the training process.
   - The Load functionality should read the saved file and restore the training process to the state it was saved in.
     - The user should be prompted to select a file location and name when the Load button is clicked.
     - The training process should be updated to reflect the loaded state, including:
       - Training metrics data
       - Model parameters
       - Training meta-parameters
       - State of the training process (Paused, Stopped, etc.)
   - Training should be able to be resumed from the end of the loaded data
   - The replay should be available once a time or range has been selected

#### Network Topology Tab

1. Fix: The top information bar of the Network Topology tab is not displaying correctly in "dark mode".
   - The top information bar should be visible and properly colored in "dark mode".
     - The text displayed in the information bar should include:
       - "Input Units: 2"
       - "Hidden Units: 6"
       - "Output Units: 1"
       - "Total Connections: 35"
     - The text color is being updated correctly.
     - The background color is not being updated correctly.
     - This means that in dark mode, the top information bar is displaying white text on a white background.

2. Fix: The "Pan" and "Lasso Select" tools should operate as expected.
   - Currently, the "Pan", "Lasso Select", and "Box Select" tools are all performing the "Box Select" function.
   - The "Pan" and "Lasso Select" tools should behave as expected.

3. Fix: Node interactions are not persisting.
   - All current node interactions/tools are being reset after ~1 second.
   - Affected tools include:
     - Zoom
     - Pan
     - Lasso Select
     - Box Select
     - Zoom In
     - Zoom Out
   - The effects of node interactions/tools should persist until changed by the user.
   - Manual resetting of the node interactions/tools should only occur when the following tools are selected:
     - "Autoscale"
     - "Reset Axes"

4. Feat: The Network Topology tab should display hidden nodes in a staggered layout.
   - Arrange the hidden nodes in a staggered layout so that all edges are displayed distinctly.
   - Use the staggered approach to improve overall visibility and aesthetics.
   - Maintain the current placement algorithm for how hidden nodes are placed vertically.
   - Modify the way the hidden nodes are placed horizontally.
     - As each new hidden node is added to the network topology tab:
       - The new node's horizontal position should be approximately 1.5 times the node's width to the right of the previous node.
   - The layout should be updated to accommodate the new node.
     - The hidden nodes should be centered horizontally between the input and output nodes.
       - The midpoint between the left-most and right-most hidden nodes should be the same as the midpoint between the input and output nodes.

5. Feat: Add mouse click events to the network topology tab to allow for selection and interaction with nodes.
   - Provide visual feedback when a node is selected.
   - Allow for interaction with selected nodes:
     - Allow mouse Left Click and Drag to move the node.
     - Allow Control + Left Click and Drag to move the entire network.
     - Allow double-Left Click to edit the node's label.
     - Allow Shift + Left Click to select multiple nodes.
     - Allow Mouse Wheel to zoom in and out.
     - Allow Right Click to open a Node context menu for changing properties or deletion.
   - Allow for the creation of new nodes by clicking on the network topology tab.

6. Feat: Indicate the most recently added node with a visual indicator.
   - When a new hidden node is added to the network topology, highlight the new node with a distinct visual indicator.
     - The visual indicator should be a glowing outline around the new node.
     - The glowing outline should be animated to pulse gently to draw attention to the new node.
   - The edges connected to the new node should also be highlighted.
     - The edge highlight should be more muted than the New Node highlight.
     - The edge highlights should remain as long as the node highlight is visible.
     - The edge highlights should be removed when the node highlight is removed.
   - The visual indicator should remain visible after the node is added.
     - If the user selects a different node while the indicator is still active, the indicator should remain on.
     - The visual indicator should remain until the user selects and moves a different node or until a new hidden node is added.
     - The visual indicator should fade out smoothly over 2 seconds.
     - The new node should receive the visual indicator as above.
   - The New Node and Edge indicators should be distinct and easily differentiated from the Selected Node indicator.

7. Feat: The "Download as an Image File" function should have a unique name suggestion.
   - Provide a default name suggestion based on the current date and time.

8. Feat: Modify the CasCor Network Architecture display to be an interactive, simulated 3D view of the network topology.
   - Allow for rotation, zooming, and panning of the network topology in 3D space.
   - Provide visual depth cues to enhance the 3D effect.
   - Allow for selection and interaction with nodes in the 3D view.
   - Retain current display layout as the default view.
   - Provide a return to default view button.
   - Maintain all current interaction features for the 3D view.
     - Allow Left Click and Drag to select and move the node.
     - Allow Control + Left Click and Drag to perform a 3D pan of the network.
     - Allow Shift + Left Click to select multiple nodes.
     - Allow double-Left Click to edit the node's label.
     - Allow Mouse Wheel to zoom in and out.
     - Allow Right Click to open a Node context menu for changing properties or deletion.
     - Allow for the creation of new nodes by clicking on the network topology tab.
   - Include additional functionality for the 3D view:
     - Add Control + Shift + Left Click and Drag to perform a 3D rotation of the network centered on the click point.
     - Add Control + Shift + Right Click and Drag to perform a 2D rotation of the network centered on the click point.

### Additional Tabs to Add

#### About Tab for Juniper Cascor backend

- Feat: Add a new tab for the "About" section.
  - This tab should display the following:
    - Application version
    - License information
    - Credits and acknowledgments
    - Links to documentation and support resources
    - Contact information for support

#### Cassandra Integration and Monitoring Tab for Juniper Cascor backend

- Feat: Add a new tab for Cassandra integration and monitoring.
  - This tab should display the following:
    - Current state of the Cassandra cluster
    - Usage Stats for Juniper Cascor backend
    - Ability to display and edit the Cassandra db schema
    - Options for managing the Cassandra cluster

#### Redis Integration and Monitoring Tab for Juniper Cascor backend

- Feat: Add a new tab for Redis integration and monitoring.
  - This tab should display the following:
    - Current state of the Redis cluster
    - Usage Stats for Juniper Cascor backend
    - Ability to display and edit the Redis db schema
    - Options for managing the Redis cluster

#### HDF5 snapshot functionality, availability, and history Tab for Juniper Cascor backend

- Feat: Add a new tab for HDF5 snapshot functionality, availability, and history.
  - This tab should display the following:
    - List of available HDF5 snapshots
    - Details about each snapshot (timestamp, size, etc.)
    - Options to create new snapshots
    - Options to restore from existing snapshots
    - History of snapshot creation and restoration activities

## Current Status of Features and Fixes on Development Roadmap

### Status per Feature

| Feature / Fix                                                                 | Status       |
|-------------------------------------------------------------------------------|--------------|
| Top Status Bar: Status/Phase fields not updating                             | Not Started  |
| Training Controls: Buttons not resetting                                      | Not Started  |
| Training Controls: Meta-parameters not applied after change                   | Not Started  |
| Training Metrics Tab: Add new tab and display metrics                        | Not Started  |
| Training Data Tab: Add new tab and display data                              | Not Started  |
| Model Architecture Tab: Add new tab and display architecture                  | Not Started  |
| About Tab for Juniper Cascor backend                                          | Not Started  |
| Cassandra Integration and Monitoring Tab                                      | Not Started  |
| Redis Integration and Monitoring Tab                                          | Not Started  |
| HDF5 Snapshot Functionality Tab                                               | Not Started  |
