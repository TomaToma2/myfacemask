'Face'# ##### BEGIN GPL LICENSE BLOCK #####
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

#-------------------------- COLORS / GROUPS EXCHANGER -------------------------#
#                                                                              #
# Vertex Color to Vertex Group allow you to convert colors channles to weight  #
# maps.                                                                        #
# The main purpose is to use vertex colors to store information when importing #
# files from other softwares. The script works with the active vertex color    #
# slot.                                                                        #
# For use the command "Vertex Clors to Vertex Groups" use the search bar       #
# (space bar).                                                                 #
#                                                                              #
#                          (c)  Alessandro Zomparelli                          #
#                                     (2017)                                   #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
################################################################################

import bpy, bmesh, os
import numpy as np
import math, timeit, time
from math import *#pi, sin
from statistics import mean, stdev
from mathutils import Vector
from numpy import *
#from .numba_functions import numba_reaction_diffusion
try: import numexpr as ne
except: pass

# Reaction-Diffusion cache
from pathlib import Path
import random, string, tempfile

from bpy.types import (
        Operator,
        Panel,
        PropertyGroup,
        )

from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
    FloatVectorProperty,
    IntVectorProperty
)

from .utils import *


def delete_all():
    for o in bpy.data.objects:
        bpy.data.objects.remove(o)
    for c in bpy.data.collections:
        bpy.data.collections.remove(c)

def set_mm():
    bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'
    bpy.context.scene.unit_settings.scale_length = 0.001
    bpy.context.space_data.overlay.grid_scale = 0.001

def set_clipping_planes():
    bpy.context.space_data.lens = 100
    bpy.context.space_data.clip_start = 1
    bpy.context.space_data.clip_end = 1e+004

class myfacemask_setup(bpy.types.Operator):
    bl_idname = "scene.myfacemask_setup"
    bl_label = "Setup scene"
    bl_description = ("Setup a new scene for MyFaceMask")
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="You are creating a new scene, all the unsaved work will be lost!", icon="ERROR")
        col.label(text="Press ESC to undo", icon='EVENT_ESC')

    def execute(self, context):

        try: context.scene.type = 'LOCAL'
        except: pass
        context.space_data.shading.show_cavity = True
        bpy.context.space_data.shading.light = 'MATCAP'
        bpy.context.space_data.overlay.show_cursor = False

        scn = context.scene

        delete_all()

        # load objects from blender file
        path = Path(os.path.dirname(os.path.realpath(__file__)))
        scene_path = path / "data" / "MyFaceMask.blend" / "Scene"
        bpy.ops.wm.append(filename="Text", directory=str(scene_path))
        scene_path = path / "data" / "MyFaceMask.blend" / "Scene"
        bpy.ops.wm.append(filename="MyFaceMask", directory=str(scene_path))

        bpy.data.scenes.remove(scn)

        set_mm()
        set_clipping_planes()

        context.space_data.shading.color_type = 'RANDOM'
        return {'FINISHED'}


class myfacemask_remesh(bpy.types.Operator):
    bl_idname = "object.myfacemask_remesh"
    bl_label = "Rebuild Mesh"
    bl_description = ("Automatically remesh surface")
    bl_options = {'REGISTER', 'UNDO'}

    detail : bpy.props.IntProperty(
        name="Detail", default=8, soft_min=3, soft_max=10,
        description="Octree Depth")

    @classmethod
    def poll(cls, context):
        try:
            ob = context.object
            exclude = ['Filter','Mask','Mask_Surface','Hole_01', 'Hole_02']
            return not context.object.hide_viewport and ob.name not in exclude
        except: return False

    def execute(self, context):
        #bpy.ops.view3d.view_selected()
        bpy.ops.object.modifier_add(type='REMESH')
        context.object.modifiers["Remesh"].mode = 'SMOOTH'
        context.object.modifiers["Remesh"].octree_depth = self.detail
        context.object.name = 'Face'
        context.object.data.materials.append(bpy.data.materials['Face_Material'])
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Remesh")
        #bpy.ops.object.shade_smooth()
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        return {'FINISHED'}

class myfacemask_mirror_border(bpy.types.Operator):
    bl_idname = "object.myfacemask_mirror_border"
    bl_label = "Mirror Border"
    bl_description = ("Symmetrize contact border")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            mod = bpy.data.objects['Mask_Surface'].modifiers['curve_project_01']
            ob = bpy.data.objects['ContourCurve']
            return context.object.name != 'Mask'
        except: return False

    def execute(self, context):
        ob = bpy.data.objects['ContourCurve']
        try:
            mod = ob.modifiers['Mirror']
            mod.show_viewport = not mod.show_viewport
        except:
            mirror = ob.modifiers.new(name='Mirror',type='MIRROR')
            project = ob.modifiers.new(name='Project',type='SHRINKWRAP')
            mirror.mirror_object = bpy.data.objects['Filter']
            mirror.use_bisect_axis[0] = True
            project.target = bpy.data.objects['Face']
        return {'FINISHED'}


class myfacemask_mirror_border_flip(bpy.types.Operator):
    bl_idname = "object.myfacemask_mirror_border_flip"
    bl_label = "Invert symmetry"
    bl_description = ("Invert border symmetry")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            ob = bpy.data.objects['ContourCurve']
            mod1 = bpy.data.objects['Mask_Surface'].modifiers['curve_project_01']
            mod = ob.modifiers['Mirror']
            return context.object.name != 'Mask' and mod.show_viewport
        except: return False

    def execute(self, context):
        ob = bpy.data.objects['ContourCurve']
        mirror = ob.modifiers['Mirror']
        mirror.use_bisect_flip_axis[0] = not mirror.use_bisect_flip_axis[0]
        return {'FINISHED'}


class myfacemask_adapt_mask(Operator):
    bl_idname = "object.myfacemask_adapt_mask"
    bl_label = "Adapt Mask"
    bl_description = ("Extract mask border based on red area")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")

    min_iso : FloatProperty(
        name="Min Value", default=0., soft_min=0, soft_max=1,
        description="Minimum weight value")
    max_iso : FloatProperty(
        name="Max Value", default=1, soft_min=0, soft_max=1,
        description="Maximum weight value")
    n_curves : IntProperty(
        name="Curves", default=10, soft_min=1, soft_max=100,
        description="Number of Contour Curves")

    in_displace : FloatProperty(
        name="Displace A", default=0, soft_min=-10, soft_max=10,
        description="Pattern displace strength")
    out_displace : FloatProperty(
        name="Displace B", default=2, soft_min=-10, soft_max=10,
        description="Pattern displace strength")

    in_steps : IntProperty(
        name="Steps A", default=1, min=0, soft_max=10,
        description="Number of layers to move inwards")
    out_steps : IntProperty(
        name="Steps B", default=1, min=0, soft_max=10,
        description="Number of layers to move outwards")
    limit_z : BoolProperty(
        name="Limit Z", default=False,
        description="Limit Pattern in Z")

    merge : BoolProperty(
        name="Merge Vertices", default=True,
        description="Merge points")
    merge_thres : FloatProperty(
        name="Merge Threshold", default=0.01, min=0, soft_max=1,
        description="Minimum Curve Radius")

    bevel_depth : FloatProperty(
        name="Bevel Depth", default=0, min=0, soft_max=1,
        description="")
    min_bevel_depth : FloatProperty(
        name="Min Bevel Depth", default=0.1, min=0, soft_max=1,
        description="")
    max_bevel_depth : FloatProperty(
        name="Max Bevel Depth", default=1, min=0, soft_max=1,
        description="")
    remove_open_curves : BoolProperty(
        name="Remove Open Curves", default=False,
        description="Remove Open Curves")

    vertex_group_pattern : StringProperty(
        name="Displace", default='',
        description="Vertex Group used for pattern displace")

    vertex_group_bevel : StringProperty(
        name="Bevel", default='',
        description="Variable Bevel depth")

    object_name : StringProperty(
        name="Active Object", default='',
        description="")

    try: vg_name = bpy.context.object.vertex_groups.active.name
    except: vg_name = ''

    vertex_group_contour : StringProperty(
        name="Contour", default=vg_name,
        description="Vertex Group used for contouring")
    clean_distance : FloatProperty(
        name="Clean Distance", default=2, min=0, soft_max=10,
        description="Remove short segments")


    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and len(ob.vertex_groups) > 0 and ob.mode == 'WEIGHT_PAINT'

    def draw(self, context):
        if not context.object.type == 'CURVE':
            self.object_name = context.object.name
        ob = bpy.data.objects[self.object_name]
        if self.vertex_group_contour not in [vg.name for vg in ob.vertex_groups]:
            self.vertex_group_contour = ob.vertex_groups.active.name
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "use_modifiers")
        col.label(text="Contour Curves:")
        col.prop_search(self, 'vertex_group_contour', ob, "vertex_groups", text='')

        col.label(text='Clean Curves:')
        col.prop(self,'clean_distance')
        #col.prop(self,'remove_open_curves')

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}
        bpy.ops.object.vertex_group_smooth(repeat=5)

        ob0 = context.object#bpy.data.objects[self.object_name]

        dg = context.evaluated_depsgraph_get()
        ob = ob0#.evaluated_get(dg)
        me0 = ob.data

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        n_verts = len(bm.verts)

        # store weight values
        try:
            weight = get_weight_numpy(ob.vertex_groups.active, len(me0.vertices))
        except:
            bm.free()
            self.report({'ERROR'}, "Please select a Vertex Group for contouring")
            return {'CANCELLED'}

        try:
            pattern_weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_pattern], len(me0.vertices))
        except:
            #self.report({'WARNING'}, "There is no Vertex Group assigned to the pattern displace")
            pattern_weight = np.zeros(len(me0.vertices))

        variable_bevel = False
        try:
            bevel_weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_bevel], len(me0.vertices))
            variable_bevel = True
        except:
            bevel_weight = np.ones(len(me0.vertices))

        #filtered_edges = bm.edges
        total_verts = np.zeros((0,3))
        total_segments = []# np.array([])

        # start iterate contours levels
        vertices, normals = get_vertices_and_normals_numpy(me0)
        filtered_edges = get_edges_id_numpy(me0)

        faces_weight = [np.array([weight[v] for v in p.vertices]) for p in me0.polygons]
        fw_min = np.array([np.min(fw) for fw in faces_weight])
        fw_max = np.array([np.max(fw) for fw in faces_weight])

        bm_faces = np.array(bm.faces)

        #print("Contour Curves, data loaded: " + str(timeit.default_timer() - start_time) + " sec")
        step_time = timeit.default_timer()
        for c in range(1):
            min_iso = min(0, 1)
            max_iso = max(0, 1)
            iso_val = 0.5

            # remove passed faces
            bool_mask = iso_val < fw_max
            bm_faces = bm_faces[bool_mask]
            fw_min = fw_min[bool_mask]
            fw_max = fw_max[bool_mask]

            # mask faces
            bool_mask = fw_min < iso_val
            faces_mask = bm_faces[bool_mask]

            count = len(total_verts)

            new_filtered_edges, edges_index, verts, bevel = contour_edges_pattern(self, c, len(total_verts), iso_val, vertices, normals, filtered_edges, weight, pattern_weight, bevel_weight)

            if verts[0,0] == None: continue
            else: filtered_edges = new_filtered_edges
            edges_id = {}
            for i, id in enumerate(edges_index): edges_id[id] = i + count

            if len(verts) == 0: continue

            # finding segments
            segments = []
            for f in faces_mask:
                seg = []
                for e in f.edges:
                    try:
                        seg.append(edges_id[e.index])
                        if len(seg) == 2:
                            segments.append(seg)
                            seg = []
                    except: pass

            total_segments = total_segments + segments
            total_verts = np.concatenate((total_verts, verts))

        if len(total_segments) > 0:
            step_time = timeit.default_timer()
            ordered_points = find_curves(total_segments, len(total_verts))

            max_len = 0
            longer_curve = [ordered_points[0]]
            for crv in ordered_points:
                pts = total_verts[np.array(crv,dtype='int')]
                print(pts.shape)
                size_x = pts.max(axis=0)[0] - pts.min(axis=0)[0]
                if max_len < size_x:
                    max_len = size_x
                    longer_curve = [crv]
            step_time = timeit.default_timer()
            crv = curve_from_pydata(total_verts, longer_curve, 'ContourCurve', self.remove_open_curves, merge_distance=self.clean_distance)
            context.view_layer.objects.active = crv
            crv.parent = ob0

            crv.select_set(True)
            ob0.select_set(False)
            crv.matrix_world = ob0.matrix_world
        else:
            bm.free()
            self.report({'ERROR'}, "There are no values in the chosen range")
            return {'CANCELLED'}
        bm.free()

        bpy.data.collections['MyFaceMask'].hide_viewport = False

        bpy.ops.object.convert(target='MESH')
        curve_object = context.object
        curve_object.hide_viewport = True

        n_verts = len(curve_object.data.vertices)
        matr = curve_object.matrix_world
        verts = [matr @ v.co for v in curve_object.data.vertices]
        mid_point = Vector((0,0,0))
        for v in verts:
            mid_point += v
        mid_point/=n_verts
        nor_vec = Vector((0,0,0))
        for i in range(n_verts-1):
            v0 = verts[i] - mid_point
            v1 = verts[i+1] - mid_point
            nor_vec += v0.cross(v1)
        nor_vec.normalize()
        if nor_vec.y > 0:
            nor_vec *= -1

        filter = bpy.data.objects['Filter']
        filter.location = mid_point + nor_vec*60
        filter.rotation_euler[0] = atan2(cos(nor_vec.y), sin(nor_vec.z))+pi
        matr = filter.matrix_local
        filter.location -= nor_vec.normalized().cross(Vector((1,0,0)))*15
        filter.location.x = 0


        ### adapt mask
        mask_srf = bpy.data.objects['Mask_Surface']
        mask_srf.modifiers['curve_project_01'].target = curve_object
        #mask_srf.modifiers['curve_project_02'].target = curve_object
        mask_srf.modifiers['avoid_face_intersections'].target = ob0
        mask_srf.modifiers['adapt_to_face'].target = ob0
        mask_srf.modifiers['adapt_to_face_02'].target = ob0

        print("Contour Curves, total time: " + str(timeit.default_timer() - start_time) + " sec")
        return {'FINISHED'}

class myfacemask_edit_mask(Operator):
    bl_idname = "object.myfacemask_edit_mask"
    bl_label = "Manual Editing"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Manually edit control points")

    @classmethod
    def poll(cls, context):
        keys = bpy.data.objects.keys()
        if 'Mask_Surface' in keys and 'Face' in keys:
            ob = bpy.data.objects['Mask_Surface']
            return ob.modifiers['adapt_to_face'].target != None
        else: return False

    def invoke(self, context, event):
        mask_srf = bpy.data.objects['Mask_Surface']
        if 'Mirror' in mask_srf.modifiers.keys():
            return context.window_manager.invoke_props_dialog(self, width=350)
        else: return self.execute(context)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="You are going to do a destructive operation", icon="ERROR")
        col.label(text="Press ESC to undo", icon='EVENT_ESC')

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in context.scene.objects: o.select_set(False)
        mask = bpy.data.objects['Mask_Surface']
        mask.select_set(True)
        bpy.context.view_layer.objects.active = mask

        face = bpy.data.objects['Face']
        face.lock_location[1] = True
        face.lock_location[0] = True
        face.lock_location[2] = True
        face.lock_rotation[0] = True
        face.lock_rotation[1] = True
        face.lock_rotation[2] = True
        face.lock_scale[0] = True
        face.lock_scale[1] = True
        face.lock_scale[2] = True

        mods = mask.modifiers.keys()
        if 'Mirror' in mods:
            bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Mirror")
        if 'Bevel' in mods:
            bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Bevel")
        if 'Subdivision' in mods:
            bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Subdivision")
        if 'curve_project_01' in mods:
            bpy.ops.object.modifier_apply(apply_as='DATA', modifier="curve_project_01")

        mask.modifiers["Hook_Border"].object = bpy.data.objects['ContourCurve']
        #bpy.ops.object.modifier_apply(apply_as='DATA', modifier="curve_project_02")
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
        bpy.ops.wm.tool_set_by_index(index=0)
        bpy.context.scene.tool_settings.use_snap = False
        bpy.context.scene.tool_settings.snap_target = 'CLOSEST'
        bpy.context.scene.tool_settings.snap_elements = {'FACE'}
        bpy.context.scene.tool_settings.use_proportional_edit = True
        bpy.context.scene.tool_settings.proportional_size = 20

        if "Hole_01" in bpy.data.objects.keys():
            bpy.data.objects["Hole_01"].hide_viewport = True
        if "Hole_02" in bpy.data.objects.keys():
            bpy.data.objects["Hole_02"].hide_viewport = True
        context.space_data.show_gizmo_object_translate = False
        context.space_data.show_gizmo_object_rotate = False

        my_areas = context.screen.areas
        for area in my_areas:
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.show_xray = False
        bpy.context.space_data.shading.type = 'SOLID'
        bpy.context.space_data.overlay.show_statvis = False

        return {'FINISHED'}


class myfacemask_edit_mask_off(Operator):
    bl_idname = "object.myfacemask_edit_mask_off"
    bl_label = "Manual Editing Off"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("End manual editing")


    @classmethod
    def poll(cls, context):
        try: return context.object.name == 'Mask_Surface'
        except: return False

    def execute(self, context):
        try:
            ob = context.object
            bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}
        except:
            return {'CANCELLED'}



class myfacemask_tag_mask_off(Operator):
    bl_idname = "object.myfacemask_tag_mask_off"
    bl_label = "Tag Mask Off"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("End manual tag insertion")

    @classmethod
    def poll(cls, context):
        ob = context.object
        try: return ob.name == 'Mask' and ob.mode != 'OBJECT'
        except: return False

    def execute(self, context):
        try:
            ob = context.object
            bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}
        except:
            return {'CANCELLED'}


class myfacemask_weight_toggle(Operator):
    bl_idname = "object.myfacemask_weight_toggle"
    bl_label = "Define area"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ('Define the area on the face using the brush tool')

    @classmethod
    def poll(cls, context):
        try:
            ob = context.object
            return ob.name == 'Face' and ob.mode != 'WEIGHT_PAINT'
        except: return False

    def execute(self, context):
        bpy.ops.paint.weight_paint_toggle()
        bpy.context.scene.tool_settings.unified_paint_settings.weight = 1
        context.tool_settings.weight_paint.brush = bpy.data.brushes['Draw']
        bpy.data.brushes["Draw"].spacing = 4
        return {'CANCELLED'}


class myfacemask_weight_add_subtract(Operator):
    bl_idname = "object.myfacemask_weight_add_subtract"
    bl_label = "Change Brush"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ('Change brush mode')

    def execute(self, context):
        val = context.scene.tool_settings.unified_paint_settings.weight
        if val < 0.5:
            context.scene.tool_settings.unified_paint_settings.weight = 1
        else:
            context.scene.tool_settings.unified_paint_settings.weight = 0
        return {'FINISHED'}


class MYFACEMASK_PT_weight(Panel):
    bl_label = "MyFaceMask"
    bl_category = "MyFaceMask"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_options = {'DEFAULT_CLOSED'}
    #bl_context = "weightpaint"

    def draw(self, context):

        try:
            ob = context.object
            mode = ob.mode
            name = ob.name
        except:
            ob = None
            mode = None
            name = ''

        layout = self.layout
        col = layout.column(align=True)
        scenes = bpy.data.scenes.keys()
        if not ('MyFaceMask' in scenes and 'Text' in scenes):
            row = col.row(align=True)
            row.scale_y = 2
            row.operator("scene.myfacemask_setup", icon="TOOL_SETTINGS")
        else:
            #col.separator()
            row = col.row(align=True)
            row.operator("ed.undo", icon='LOOP_BACK')
            row.operator("ed.redo", icon='LOOP_FORWARDS')
            col.separator()
            col.label(text="Import scan:", icon="OUTLINER_OB_ARMATURE")
            row = col.row(align=True)
            row.operator("import_scene.obj", text="OBJ", icon='IMPORT')
            row.operator("import_mesh.stl", text="STL", icon='IMPORT')
            col.separator()
            col.operator("object.myfacemask_remesh", icon="MOD_REMESH", text="Remesh")
            col.separator()
            col.label(text="Adapt mask:")
            col.operator("object.myfacemask_weight_toggle", icon="BRUSH_DATA", text="Define area")

            if mode == 'WEIGHT_PAINT':
                weight = context.scene.tool_settings.unified_paint_settings.weight
                if weight < 0.5:
                    col.operator("object.myfacemask_weight_add_subtract", icon="SELECT_EXTEND", text='Add')
                else:
                    col.operator("object.myfacemask_weight_add_subtract", icon="SELECT_SUBTRACT", text='Subtract')
                #col.prop(context.scene.tool_settings.unified_paint_settings, 'weight')
                col.prop(context.scene.tool_settings.unified_paint_settings, 'size')
                col.separator()

            col.operator("object.myfacemask_adapt_mask", icon="USER", text='Adapt mask')
            col.separator()
            try:
                curve = bpy.data.objects['ContourCurve']
                mirror = curve.modifiers['Mirror'].show_viewport
            except: mirror = False
            if mirror:
                col.operator("object.myfacemask_mirror_border", icon="MOD_MIRROR", text="Symmetric border off")
            else:
                col.operator("object.myfacemask_mirror_border", icon="MOD_MIRROR", text="Symmetric border on")
            col.operator("object.myfacemask_mirror_border_flip", icon="ARROW_LEFTRIGHT", text="Invert symmetry")

            col.separator()
            col.label(text="Adjust:")
            set_bool = False
            my_areas = context.screen.areas
            for area in my_areas:
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        set_bool = not space.shading.show_xray
            if set_bool:
                col.operator("object.myfacemask_place_filter", icon="GIZMO", text='Align filter on')
            else:
                col.operator("object.myfacemask_place_filter", icon="GIZMO", text='Align filter off')
            col.separator()

            if mode != 'EDIT':
                col.operator("object.myfacemask_edit_mask", icon="EDITMODE_HLT", text="Manual editing")
                col.separator()
            else:
                col.operator("object.myfacemask_edit_mask_off", icon="OBJECT_DATA", text="End editing")
                col.separator()

            if 'Hole_01' in bpy.data.objects.keys():
                hole = bpy.data.objects['Hole_01']
            elif 'Hole_02' in bpy.data.objects.keys():
                hole = bpy.data.objects['Hole_02']
            else:
                hole = None
            if hole != None:
                if hole.hide_viewport:
                    col.operator("object.myfacemask_holes_snap", icon="CLIPUV_DEHLT", text="Show holes")
                else:
                    col.operator("object.myfacemask_holes_snap", icon="CLIPUV_DEHLT", text="Hide holes")

            if name != 'Mask' and name != '':
                col.separator()
                mask = bpy.data.objects['Mask_Surface']
                mod = mask.modifiers['Displace']
                col.prop(mod, 'strength', text='Nose pressure')
                mod = mask.modifiers['Thickness']
                col.prop(mod, 'thickness', text='Thickness')
                mod = mask.modifiers['avoid_face_intersections']
                col.prop(mod, 'offset', text='Offset')

            col.separator()
            col.label(text="Prepare 3D print:")
            col.operator("object.myfacemask_boolean", icon="MATSHADERBALL", text="Prepare model")
            col.separator()

            col.label(text="Identity:")
            if mode != 'SCULPT':
                col.prop(context.scene, 'myfacemask_id', text='', icon='COPY_ID')
                col.operator('scene.myfacemask_generate_tag', icon='LINE_DATA')
                col.separator()
                col.label(text="Export:")
                col.operator("export_mesh.stl", text="STL", icon='EXPORT')
            else:
                col.operator('object.myfacemask_tag_mask_off', icon='OBJECT_DATA', text='Done')

class myfacemask_generate_tag(Operator):
    bl_idname = "scene.myfacemask_generate_tag"
    bl_label = "Insert tag"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Manually add ID tag")

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.myfacemask_id != '' and context.object.name == 'Mask'
        except: return False

    def execute(self, context):
        text_scene = bpy.data.scenes['Text']
        code = context.scene.myfacemask_id
        if code == '': code = 'WASP'
        text_scene.objects['Text'].data.body = code
        #image_path = bpy.context.preferences.filepaths.temporary_directory + "\\tag.png"
        image_path = str(Path(tempfile.gettempdir()) / 'tag.png')
        text_scene.render.filepath = image_path
        bpy.ops.render.render(scene='Text', write_still=1)

        for o in context.scene.objects: o.select_set(False)
        mask = bpy.data.objects['Mask']
        mask.select_set(True)
        bpy.context.view_layer.objects.active = mask

        # create sculpt mask
        bpy.ops.object.mode_set(mode='SCULPT')

        me = mask.data
        #verts = [v.select for v in me.vertices]
        bm = bmesh.new()
        bm.from_mesh(me)
        if not bm.verts.layers.paint_mask:
            m = bm.verts.layers.paint_mask.new()
        else:
            m = bm.verts.layers.paint_mask[0]
        for v in bm.verts:
            v[m] = v.co.z < 11
        bm.to_mesh(me)
        bm.clear()
        me.update()

        # generate brush texture
        tex = bpy.data.textures.new('TAG','IMAGE')
        img = bpy.data.images.load(filepath=image_path)
        tex.image = img
        brush = bpy.data.brushes["SculptDraw"]
        context.tool_settings.sculpt.brush.sculpt_tool = 'DRAW'
        context.tool_settings.sculpt.brush = brush
        brush.texture_slot.texture = tex
        brush.texture_slot.map_mode = 'AREA_PLANE'
        brush.curve_preset = 'CONSTANT'
        brush.strength = 0.2
        context.scene.tool_settings.unified_paint_settings.size = 250
        #brush.direction = 'SUBTRACT'

        bpy.ops.sculpt.dynamic_topology_toggle()
        context.scene.tool_settings.sculpt.detail_size = 1
        return {'FINISHED'}

class myfacemask_boolean(Operator):
    bl_idname = "object.myfacemask_boolean"
    bl_label = "Prepare model"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Prepare model for 3D printing")

    @classmethod
    def poll(cls, context):
        try:
            ob = bpy.data.objects['Mask_Surface']
            return ob.modifiers['adapt_to_face'].target != None
        except: return False

    def execute(self, context):
        scene = context.scene
        for o in scene.objects: o.select_set(False)

        surf = bpy.data.objects['Mask_Surface']
        surf.select_set(True)
        bpy.context.view_layer.objects.active = surf
        thickness = surf.modifiers['Thickness'].thickness
        for m in surf.modifiers:
            try:
                bpy.ops.object.modifier_apply(apply_as='DATA', modifier=m.name)
            except: pass
        surf.data.update()
        me = surf.data
        n_verts = len(me.vertices)
        n_half = int(n_verts/2)
        for i in range(n_half):
            v0 = me.vertices[i]
            v1 = me.vertices[i+n_half]
            v2 = v1.co-v0.co
            v2 = Vector((v2.x,v2.y,0))
            v1.co = v2.normalized()*thickness + v0.co

        filter = bpy.data.objects['Filter']
        filter.select_set(True)
        bpy.context.view_layer.objects.active = filter
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.duplicate_move()

        ob = context.object
        ob.name = 'Mask'
        for m in ob.modifiers: m.show_viewport = True
        for m in ob.modifiers:
            try:
                bpy.ops.object.modifier_apply(apply_as='DATA', modifier=m.name)
            except:
                ob.modifiers.remove(m)
        bpy.ops.object.location_clear(clear_delta=False)
        bpy.ops.object.rotation_clear(clear_delta=False)
        bpy.ops.view3d.view_selected()
        for o in scene.objects: o.hide_viewport = True
        ob.hide_viewport = False
        ob.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.space_data.overlay.show_statvis = True
        bpy.context.scene.tool_settings.statvis.type = 'OVERHANG'
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.context.scene.tool_settings.use_snap = False
        return {'FINISHED'}

class myfacemask_holes_snap(Operator):
    bl_idname = "object.myfacemask_holes_snap"
    bl_label = "Place holes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Manually place holes")

    @classmethod
    def poll(cls, context):
        try:
            ob = bpy.data.objects['Mask_Surface']
            return ob.modifiers['adapt_to_face'].target != None and context.object.mode == 'OBJECT'
        except: return False

    def execute(self, context):
        objects = bpy.data.objects

        my_areas = bpy.context.screen.areas
        for area in my_areas:
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.show_xray = False
        context.scene.tool_settings.use_snap = False

        if "Hole_01" in objects.keys():
            set_bool = objects["Hole_01"].hide_viewport
        if "Hole_02" in objects.keys():
            set_bool = objects["Hole_02"].hide_viewport

        if set_bool:
            bpy.data.objects['Mask_Surface'].select_set(True)
            bpy.ops.view3d.view_axis(type='RIGHT')
            bpy.ops.view3d.view_selected()
            bpy.data.objects['Mask_Surface'].select_set(False)

        context.space_data.show_gizmo_object_translate = set_bool
        context.space_data.show_gizmo_object_rotate = False
        hole = None
        if 'Hole_01' in bpy.data.objects.keys():
            hole = objects["Hole_01"]
            hole.hide_viewport = not set_bool
        if 'Hole_02' in bpy.data.objects.keys():
            hole = objects["Hole_02"]
            hole.hide_viewport = not set_bool
        for o in objects: o.select_set(False)
        hole.select_set(True)
        context.view_layer.objects.active = hole
        return {'FINISHED'}

class myfacemask_place_filter(Operator):
    bl_idname = "object.myfacemask_place_filter"
    bl_label = "Align filter"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Manually align position and rotation of the filter")

    @classmethod
    def poll(cls, context):
        try:
            ob = bpy.data.objects['Filter']
            ob = bpy.data.objects['Mask_Surface']
            return ob.modifiers['adapt_to_face'].target != None
        except: return False

    def execute(self, context):
        ob = bpy.data.objects['Filter']
        for o in bpy.data.objects: o.select_set(False)
        set_bool = False
        my_areas = bpy.context.screen.areas
        for area in my_areas:
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    set_bool = not space.shading.show_xray
                    space.shading.show_xray = set_bool
        if set_bool:
            ob.select_set(True)
            context.view_layer.objects.active = ob
            bpy.data.objects['Mask_Surface'].select_set(True)
            bpy.ops.view3d.view_axis(type='RIGHT')
            bpy.ops.view3d.view_selected()
            bpy.data.objects['Mask_Surface'].select_set(False)
        context.space_data.show_gizmo_object_translate = set_bool
        context.space_data.show_gizmo_object_rotate = set_bool
        context.scene.tool_settings.use_snap = False
        return {'FINISHED'}


def contour_edges_pattern(operator, c, verts_count, iso_val, vertices, normals, filtered_edges, weight, pattern_weight, bevel_weight):
    # vertices indexes
    id0 = filtered_edges[:,0]
    id1 = filtered_edges[:,1]
    # vertices weight
    w0 = weight[id0]
    w1 = weight[id1]
    # weight condition
    bool_w0 = w0 < iso_val
    bool_w1 = w1 < iso_val

    # mask all edges that have one weight value below the iso value
    mask_new_verts = np.logical_xor(bool_w0, bool_w1)
    if not mask_new_verts.any():
        return np.array([[None]]), {}, np.array([[None]]), np.array([[None]])

    id0 = id0[mask_new_verts]
    id1 = id1[mask_new_verts]
    # filter arrays
    v0 = vertices[id0]
    v1 = vertices[id1]
    n0 = normals[id0]
    n1 = normals[id1]
    w0 = w0[mask_new_verts]
    w1 = w1[mask_new_verts]
    pattern0 = pattern_weight[id0]
    pattern1 = pattern_weight[id1]
    try:
        bevel0 = bevel_weight[id0]
        bevel1 = bevel_weight[id1]
    except: pass
    param = (iso_val-w0)/(w1-w0)
    # pattern displace
    #mult = 1 if c%2 == 0 else -1
    if c%(operator.in_steps + operator.out_steps) < operator.in_steps:
        mult = operator.in_displace
    else:
        mult = operator.out_displace
    pattern_value = pattern0 + (pattern1-pattern0)*param
    try:
        bevel_value = bevel0 + (bevel1-bevel0)*param
        bevel_value = np.expand_dims(bevel_value,axis=1)
    except: bevel_value = None
    disp = pattern_value * mult
    param = np.expand_dims(param,axis=1)
    disp = np.expand_dims(disp,axis=1)
    verts = v0 + (v1-v0)*param
    norm = n0 + (n1-n0)*param
    if operator.limit_z: disp *= 1-abs(np.expand_dims(norm[:,2], axis=1))
    verts = verts + norm*disp

    # indexes of edges with new vertices
    edges_index = filtered_edges[mask_new_verts][:,2]

    # remove all edges completely below the iso value
    #mask_edges = np.logical_not(np.logical_and(bool_w0, bool_w1))
    #filtered_edges = filtered_edges[mask_edges]
    return filtered_edges, edges_index, verts, bevel_value

def contour_edges_pattern_eval(operator, c, verts_count, iso_val, vertices, normals, filtered_edges, weight, pattern_weight):
    # vertices indexes
    id0 = eval('filtered_edges[:,0]')
    id1 = eval('filtered_edges[:,1]')
    # vertices weight
    w0 = eval('weight[id0]')
    w1 = eval('weight[id1]')
    # weight condition
    bool_w0 = ne.evaluate('w0 < iso_val')
    bool_w1 = ne.evaluate('w1 < iso_val')

    # mask all edges that have one weight value below the iso value
    mask_new_verts = eval('np.logical_xor(bool_w0, bool_w1)')
    if not mask_new_verts.any(): return np.array([[None]]), {}, np.array([[None]])

    id0 = eval('id0[mask_new_verts]')
    id1 = eval('id1[mask_new_verts]')
    # filter arrays
    v0 = eval('vertices[id0]')
    v1 = eval('vertices[id1]')
    n0 = eval('normals[id0]')
    n1 = eval('normals[id1]')
    w0 = eval('w0[mask_new_verts]')
    w1 = eval('w1[mask_new_verts]')
    pattern0 = eval('pattern_weight[id0]')
    pattern1 = eval('pattern_weight[id1]')
    param = ne.evaluate('(iso_val-w0)/(w1-w0)')
    # pattern displace
    #mult = 1 if c%2 == 0 else -1
    if c%(operator.in_steps + operator.out_steps) < operator.in_steps:
        mult = -operator.in_displace
    else:
        mult = operator.out_displace
    pattern_value = eval('pattern0 + (pattern1-pattern0)*param')
    disp = ne.evaluate('pattern_value * mult')
    param = eval('np.expand_dims(param,axis=1)')
    disp = eval('np.expand_dims(disp,axis=1)')
    verts = ne.evaluate('v0 + (v1-v0)*param')
    norm = ne.evaluate('n0 + (n1-n0)*param')
    if operator.limit_z:
        mult = eval('1-abs(np.expand_dims(norm[:,2], axis=1))')
        disp = ne.evaluate('disp * mult')
    verts = ne.evaluate('verts + norm*disp')

    # indexes of edges with new vertices
    edges_index = eval('filtered_edges[mask_new_verts][:,2]')

    # remove all edges completely below the iso value
    mask_edges = eval('np.logical_not(np.logical_and(bool_w0, bool_w1))')
    filtered_edges = eval('filtered_edges[mask_edges]')
    return filtered_edges, edges_index, verts


def contour_bmesh(me, bm, weight, iso_val):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # store weight values

    vertices = get_vertices_numpy(me)
    faces_mask = np.array(bm.faces)
    filtered_edges = get_edges_id_numpy(me)
    n_verts = len(bm.verts)

    #############################

    # vertices indexes
    id0 = filtered_edges[:,0]
    id1 = filtered_edges[:,1]
    # vertices weight
    w0 = weight[id0]
    w1 = weight[id1]
    # weight condition
    bool_w0 = w0 < iso_val
    bool_w1 = w1 < iso_val

    # mask all edges that have one weight value below the iso value
    mask_new_verts = np.logical_xor(bool_w0, bool_w1)
    if not mask_new_verts.any(): return np.array([[None]]), {}, np.array([[None]])

    id0 = id0[mask_new_verts]
    id1 = id1[mask_new_verts]
    # filter arrays
    v0 = vertices[id0]
    v1 = vertices[id1]
    w0 = w0[mask_new_verts]
    w1 = w1[mask_new_verts]
    param = (iso_val-w0)/(w1-w0)
    param = np.expand_dims(param,axis=1)
    verts = v0 + (v1-v0)*param

    # indexes of edges with new vertices
    #edges_index = filtered_edges[mask_new_verts][:,2]

    edges_id = {}
    for i, e in enumerate(filtered_edges):
        #edges_id[id] = i + n_verts
        edges_id['{}_{}'.format(e[0],e[1])] = i + n_verts
        edges_id['{}_{}'.format(e[1],e[0])] = i + n_verts

    splitted_faces = []

    switch = False
    # splitting faces
    for f in faces_mask:
        # create sub-faces slots. Once a new vertex is reached it will
        # change slot, storing the next vertices for a new face.
        build_faces = [[],[]]
        #switch = False
        verts0 = list(me.polygons[f.index].vertices)
        verts1 = list(verts0)
        verts1.append(verts1.pop(0)) # shift list
        for id0, id1 in zip(verts0, verts1):

            # add first vertex to active slot
            build_faces[switch].append(id0)

            # try to split edge
            try:
                # check if the edge must be splitted
                new_vert = edges_id['{}_{}'.format(id0,id1)]
                # add new vertex
                build_faces[switch].append(new_vert)
                # if there is an open face on the other slot
                if len(build_faces[not switch]) > 0:
                    # store actual face
                    splitted_faces.append(build_faces[switch])
                    # reset actual faces and switch
                    build_faces[switch] = []
                    # change face slot
                switch = not switch
                # continue previous face
                build_faces[switch].append(new_vert)
            except: pass
        if len(build_faces[not switch]) == 2:
            build_faces[not switch].append(id0)
        if len(build_faces[not switch]) > 2:
            splitted_faces.append(build_faces[not switch])
        # add last face
        splitted_faces.append(build_faces[switch])

    # adding new vertices use fast local method access
    _new_vert = bm.verts.new
    for v in verts: _new_vert(v)
    bm.verts.ensure_lookup_table()

    # deleting old edges/faces
    bm.edges.ensure_lookup_table()
    remove_edges = [bm.edges[i] for i in filtered_edges[:,2]]
    #for e in remove_edges: bm.edges.remove(e)
    #for e in delete_edges: bm.edges.remove(e)

    bm.verts.ensure_lookup_table()
    # adding new faces use fast local method access
    _new_face = bm.faces.new
    missed_faces = []
    for f in splitted_faces:
        try:
            face_verts = [bm.verts[i] for i in f]
            _new_face(face_verts)
        except:
            missed_faces.append(f)

    #me = bpy.data.meshes.new('_tissue_tmp_')
    bm.to_mesh(me)
    weight = np.concatenate((weight, np.ones(len(verts))*iso_val))

    return me, bm, weight
