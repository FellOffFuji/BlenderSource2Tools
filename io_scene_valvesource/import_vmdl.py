#  Copyright (c) 2014 Tom Edwards contact@steamreview.org
#
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import math
import re
from bpy_extras.io_utils import ImportHelper
from mathutils import Euler


def parse_vmdl_attachments(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read the entire content as a single string, necessary for re.DOTALL
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

    attachments_data = []

    # Regex to capture the entire 'Attachment' block, including newlines (re.DOTALL)
    attachment_pattern = re.compile(
        r'{\s*_class = "Attachment"(.*?)}',
        re.DOTALL
    )

    array_pattern = re.compile(
        r'(relative_origin|relative_angles|origin|angles)\s+=\s*\[(.*?)\]',
        re.DOTALL | re.IGNORECASE
    )

    for block in attachment_pattern.findall(content):
        attachment = {}

        name_match = re.search(r'name\s+=\s+"(.*?)"', block)
        if name_match:
            attachment['name'] = name_match.group(1)

        bone_match = re.search(r'parent_bone\s+=\s+"(.*?)"', block)
        if bone_match:
            attachment['parent_bone'] = bone_match.group(1)


        for match in array_pattern.finditer(block):
            key = match.group(1).lower()
            array_content = match.group(2)  # The raw content inside the brackets

            coords = []
            try:
                coords = [
                    float(c.strip())
                    for c in array_content.split(',')
                    if c.strip()
                ]
            except ValueError:
                print(
                    f"Warning: Could not convert coordinates for {key} in attachment {attachment.get('name', 'UNKNOWN')}.")
                continue

            if 'origin' in key:
                attachment['origin'] = coords
            elif 'angles' in key:
                attachment['angles'] = coords


        if 'name' in attachment and 'origin' in attachment and len(
                attachment['origin']) == 3 and 'angles' in attachment and len(attachment['angles']) == 3:
            attachments_data.append(attachment)

    return attachments_data


class VmdlAttachmentImporter(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.vmdl_attachments"
    bl_label = "Import VMDL Attachments"
    bl_description = "Import Deadlock VMDL attachment data and generate attachment points."
    bl_options = {'UNDO', 'PRESET'}

    TARGET_ATTACHMENT_NAMES = {
        "far_00", "far_01", "far_02",
        "near_00", "near_01", "near_02",
        "gunaim_00", "gunaim_01", "gunaim_02"
    }

    # File browser properties
    filepath: bpy.props.StringProperty(name="File Path", maxlen=1024, default="", options={'HIDDEN'})
    filter_glob: bpy.props.StringProperty(default="*.vmdl", options={'HIDDEN'})

    filter_mode: bpy.props.EnumProperty(
        name="Attachment Filter",
        description="Filter which attachments to import.",
        items=[
            ('ALL', "All Attachments", "Import all attachments found in the VMDL file."),
            ('WEAPON_POINTS', "Weapon Aim Points", "Only import: far_xx, near_xx, and gunaim_xx."),
        ],
        default='ALL',
    )

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No file selected.")
            return {'CANCELLED'}

        attachments_data = parse_vmdl_attachments(self.filepath)

        filtered_attachments = attachments_data

        if self.filter_mode == 'WEAPON_POINTS':
            filtered_attachments = [
                att for att in attachments_data
                if att.get('name') in self.TARGET_ATTACHMENT_NAMES
            ]

            if not filtered_attachments:
                self.report({'WARNING'}, "Filter is active, but no matching weapon attachments were found in the file.")
                return {'FINISHED'}

            self.report({'INFO'}, f"Filtered down to {len(filtered_attachments)} weapon attachments.")
        # -----------------------------

        if not filtered_attachments:
            self.report({'WARNING'}, "No attachment data found in file after parsing/filtering.")
            return {'FINISHED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.create_attachment_objects(context, filtered_attachments)

        self.report({'INFO'}, f"Successfully imported {len(filtered_attachments)} standalone attachments.")
        return {'FINISHED'}

    def create_attachment_objects(self, context, attachments_data):

        collection_name = "VMDL_Attachments"
        if collection_name not in bpy.data.collections:
            attachment_collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(attachment_collection)
        else:
            attachment_collection = bpy.data.collections[collection_name]

        for att in attachments_data:
            name = att["name"]
            origin_coords = att["origin"]
            angle_coords = att["angles"]

            location = (
                origin_coords[0],
                origin_coords[1],
                origin_coords[2],
            )

            rotation = Euler((
                math.radians(angle_coords[0]),
                math.radians(angle_coords[1]),
                math.radians(angle_coords[2]),
            ), 'YZX')


            bpy.ops.object.empty_add(type='SINGLE_ARROW', location=location)
            att_empty = context.active_object
            att_empty.name = name
            att_empty.empty_display_size = 80.0

            att_empty.rotation_euler = rotation

            for col in att_empty.users_collection:
                if col.name == "Collection":
                    continue
                col.objects.unlink(att_empty)
            attachment_collection.objects.link(att_empty)

            self.report({'INFO'}, f"Created standalone attachment point '{name}'.")