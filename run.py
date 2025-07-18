import os
import sys
import json
import math
import random
import argparse
import shutil

#lets assume 948x948 LUTs, into 6-> each bit represents 138 LUT widths 

def setup():
    # Set PROJECT_ROOT to the directory where this script is located
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.environ['PROJECT_ROOT'] = project_root

    systems_dir = os.path.join(project_root, 'systems')
    if not os.path.isdir(systems_dir):
        print(f"'systems' directory not found at {systems_dir}")
        return []

    folder_paths = []
    for filename in os.listdir(systems_dir):
        if filename.endswith('.json'):
            folder_name = os.path.splitext(filename)[0] + '_system_config'
            folder_path = os.path.join(project_root, folder_name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                print(f"Created folder: {folder_path}")
            else:
                print(f"Folder already exists: {folder_path}")
            folder_paths.append(folder_path)
    return folder_paths

def parse_json_to_vars(json_path):
    """
    Parses the JSON file at json_path and returns a dictionary
    with all its key-value pairs as variables.
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data

def print_json_data(json_path):
    """
    Prints the contents of the JSON file at json_path.
    """
    data = parse_json_to_vars(json_path)
    for key, value in data.items():
        print(f"{key}: {value}")

def calculate_placement(data):
    """
    Calculates the placement of blocks based on their LUT count and Placement bits.
    Returns a dictionary mapping ID to coordinates [(x1,y1), (x2,y2)].
    
    Each placement bit represents 135 LUTs in width.
    The LUT count determines the area of the block.
    Blocks are placed from top to bottom at the next available spot.
    Each 158 LUT section is treated independently for placement.
    """
    placements = {}
    
    # Track the highest used y-coordinate for each bit position
    bit_y_occupied = {}  # Maps bit position to max y used
    
    for block in data:
        if 'ID' not in block or 'LUT' not in block or 'Placement' not in block:
            continue  # Skip blocks without required info
            
        block_id = block['ID']
        lut_count = block['LUT']
        placement_bits = block['Placement']
        
        if lut_count is None:
            continue  # Skip blocks with no LUT count
        
        # Find positions where bits are set to 1
        positions = [i for i, bit in enumerate(placement_bits) if bit == '1']
        
        if not positions:
            continue  # Skip if no positions are set
        
        # Calculate width (number of bits set × 135)
        width = len(positions) * 135
        
        # Calculate height based on LUT area divided by width, rounded up
        height = math.ceil(lut_count / width)
        
        # Calculate x1 and x2
        x1 = min(positions) * 135
        x2 = x1 + width
        
        # Find the next available y-coordinate (top to bottom)
        # Only consider the bit positions this block will occupy
        max_y = 0
        for bit_pos in positions:
            if bit_pos in bit_y_occupied:
                max_y = max(max_y, bit_y_occupied[bit_pos])
        
        y1 = max_y
        y2 = y1 + height
        
        # Update y_occupied for only the bit positions this block occupies
        for bit_pos in positions:
            bit_y_occupied[bit_pos] = y2
        
        placements[block_id] = [(x1, y1), (x2, y2)]
    
    return placements

def get_bounding_box(placements):
    x_coords = [coord[0][0] for coord in placements.values()] + [coord[1][0] for coord in placements.values()]
    y_coords = [coord[0][1] for coord in placements.values()] + [coord[1][1] for coord in placements.values()]
    return min(x_coords), max(x_coords), min(y_coords), max(y_coords)

def get_mesh_endpoint_positions(x1, x2, y1, y2, mesh_dim):
    endpoints = []
    for j in range(mesh_dim):
        for i in range(mesh_dim):
            x = (948) * (i+1) / (mesh_dim+1)
            y = (948) * (j+1) / (mesh_dim+1)
            endpoints.append((x, y))
    return endpoints

def assign_endpoints_to_single_block(placements, mesh_dim):
    x1, x2, y1, y2 = get_bounding_box(placements)
    endpoints = get_mesh_endpoint_positions(x1, x2, y1, y2, mesh_dim)

    block_to_endpoints = {}

    for block_id, ((bx1, by1), (bx2, by2)) in placements.items():
        assigned_eids = []
        for eid, (ex, ey) in enumerate(endpoints):
            if bx1 <= ex <= bx2 and by1 <= ey <= by2:
                assigned_eids.append(eid)

        if assigned_eids:
            block_to_endpoints[block_id] = assigned_eids
        else:
            # No endpoints inside → assign nearest one
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
            min_dist = float('inf')
            closest_eid = None
            for eid, (ex, ey) in enumerate(endpoints):
                dist = (cx - ex) ** 2 + (cy - ey) ** 2
                if dist < min_dist:
                    min_dist = dist
                    closest_eid = eid
            block_to_endpoints[block_id] = [closest_eid]

    return block_to_endpoints, endpoints

def sweep_mesh_granularity(placements, project_root):
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    output_root = os.path.join(project_root, 'granularity_iteration')

    if os.path.exists(output_root):
        shutil.rmtree(output_root)
    os.makedirs(output_root)

    for mesh_dim in range(1, 15):
        subdir = os.path.join(output_root, f"{mesh_dim}x{mesh_dim}_granularity")
        os.makedirs(subdir, exist_ok=True)

        # Assign endpoint-block mapping
        block_to_endpoints, endpoint_coords = assign_endpoints_to_single_block(placements, mesh_dim)
        

        
        # if len(block_to_endpoints) != len(placements):
        #     shutil.rmtree(subdir)
        #     continue
    
        # Save text file
        txt_path = os.path.join(subdir, "block_to_endpoints.txt")
        with open(txt_path, "w") as f:
            for block_id in sorted(block_to_endpoints.keys()):
                endpoints = block_to_endpoints[block_id]
                f.write(f"Block_{block_id} Endpoints = {endpoints}\n")

        png_path = os.path.join(subdir, "placement.png")
        visualize_placement(placements, endpoint_coords, save_path=png_path)

        

        

def visualize_placement(placements, endpoints=None, save_path=None):
    """
    Visualizes the block placements.
    
    Args:
        placements: Dictionary mapping block IDs to coordinates [(x1,y1), (x2,y2)]
    """
    # Import matplotlib only when this function is called
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Set up color cycle (different color for each block)
    colors = plt.cm.tab10.colors
    
    # Draw each block as a rectangle
    for block_id, coords in placements.items():
        (x1, y1), (x2, y2) = coords
        width = x2 - x1
        height = y2 - y1
        
        # Get a color for this block (cycling through available colors)
        color = colors[int(block_id) % len(colors)]
        
        # Create rectangle
        rect = patches.Rectangle((x1, y1), width, height, linewidth=1, 
                                edgecolor='black', facecolor=color, alpha=0.7)
        ax.add_patch(rect)
        
        # Add block ID as text in the center of the rectangle
        ax.text(x1 + width/2, y1 + height/2, f"ID: {block_id}", 
                ha='center', va='center', fontsize=10, color='black')

    # Optional: draw endpoints
    if endpoints:
        for idx, (ex, ey) in enumerate(endpoints):
            ax.plot(ex, ey, 'rx')  # Red X marker
            ax.text(ex + 10, ey + 10, f"EP {idx}", color='red', fontsize=8)
    
    # Set axis limits with some padding
    ax.set_xlim(0, 950)
    ax.set_ylim(0, 950)
    
    # Add labels and title
    ax.set_xlabel('X position (LUT units)')
    ax.set_ylabel('Y position (LUT units)')
    ax.set_title('Block Placement Visualization')
    
    # Add grid for better readability
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Show the plot
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()

# Add this to your main function:
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Process and visualize block placements.')
    parser.add_argument('--no-visualize', action='store_true', help='Disable visualization')
    args = parser.parse_args()
    
    # Set up project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.environ['PROJECT_ROOT'] = project_root
    
    # Path to video.json
    json_path = os.path.join(project_root, 'systems', 'video.json')
    
    # Check if the file exists
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        return
    
    # Parse JSON data
    data = parse_json_to_vars(json_path)
    
    # Calculate placements
    placements = calculate_placement(data)
    
    # Print ID:placement pairs
    print("ID:Placement Pairs:")
    for block_id, coords in placements.items():
        print(f"ID {block_id}: {coords}")

    sweep_mesh_granularity(placements, project_root)
    
    # Visualize the placements only if not disabled
    if not args.no_visualize:
        try:
            visualize_placement(placements)
        except ModuleNotFoundError:
            print("Visualization failed: matplotlib is not installed")
            print("Install matplotlib with: pip install matplotlib")
            print("Or continue to run with --no-visualize flag")
        except Exception as e:
            print(f"Visualization failed: {e}")
            print("Try running with --no-visualize if you're having issues with matplotlib")

if __name__ == "__main__":
    main()