import ifcopenshell
import ifcopenshell.geom
from ifcopenshell.util import shape
from ifcopenshell.util.element import get_container

# Set up geometry settings for area calculation
settings = ifcopenshell.geom.settings()
settings.set(settings.DISABLE_OPENING_SUBTRACTIONS, False)

#TODO add office check and atrium and meeting rooms https://timmcginley.github.io/41936/Project/index.html#s05-meeting-rooms

# get the model
num = "15"
part = "C"
year = "25"
#file = ifcopenshell.open('models/ARCH_B112_IFC4.ifc')
loc ="C:/Users/TIMMC/OneDrive - Danmarks Tekniske Universitet/Skrivebord/36"+year+part+"/BIM/"


file = ifcopenshell.open(loc + num + '/'+year+'-'+num+'-'+part+'-ARCH.ifc')
#file = ifcopenshell.open(loc + num + '/26-01-C-Existing building308.ifc')

spaces = file.by_type("IfcSpace")
print("Team: " + num+" "+year+" "+part)
print("IFC SCHEMA: " + file.schema)

if file.schema == "IFC4" or file.schema == "IFC4X3":
    schema = "[PASS] " + file.schema
else:
    schema = "[FAIL] " + file.schema  

# get the spaces and calculate their areas
print("There are {} spaces in the IFC file:" .format(len(spaces)))


def get_area(space):    
    # Try direct numeric attributes first
    def _value_to_number(val):
        try:
            return float(getattr(val, 'wrappedValue', val))
        except Exception:
            try:
                return float(val)
            except Exception:
                return None

    for attr in ("Area", "NetFloorArea", "GrossFloorArea"):
        if hasattr(space, attr):
            v = getattr(space, attr)
            n = _value_to_number(v)
            if n is not None:
                return n

    # Look in property sets for area-like properties
    if hasattr(space, 'IsDefinedBy'):
        for rel in space.IsDefinedBy:
            propdef = getattr(rel, 'RelatingPropertyDefinition', None)
            if propdef is None:
                continue
            if propdef.is_a('IfcPropertySet'):
                for prop in getattr(propdef, 'HasProperties', ()): 
                    if prop.is_a('IfcPropertySingleValue'):
                        name = str(getattr(prop, 'Name', '')).lower()
                        if 'area' in name:
                            nominal = getattr(prop, 'NominalValue', None)
                            n = _value_to_number(nominal)
                            if n is not None:
                                return n

    # Try geometry-based calculation (may raise RuntimeError if representation is NULL)
    try:
        shape_data = ifcopenshell.geom.create_shape(settings, space)
        try:
            area = shape.get_footprint_area(shape_data.geometry)
            return float(area)
        except Exception:
            pass
    except RuntimeError:
        # Representation is NULL or other geometry error; fall through
        pass
    except Exception:
        pass

    return None


def get_storey(space, model):
    # 1) Preferred: use get_container util (works in many cases)
    try:
        container = get_container(space)
        if container is not None and container.is_a('IfcBuildingStorey'):
            return container
    except Exception:
        pass

    # 2) Check common inverse relations on the space itself
    for rel_name in ('IsContainedInStructure', 'ContainedInStructure', 'IsDefinedBy'):
        if hasattr(space, rel_name):
            for rel in getattr(space, rel_name):
                for attr in ('RelatingStructure', 'RelatingBuildingStorey', 'RelatingSpatialStructure'):
                    struct = getattr(rel, attr, None)
                    if struct is not None and struct.is_a('IfcBuildingStorey'):
                        return struct

    # 3) Scan RelContainedInSpatialStructure relations in the model
    try:
        for rel in model.by_type('IfcRelContainedInSpatialStructure'):
            related = getattr(rel, 'RelatedElements', ())
            if space in related:
                for attr in ('RelatingStructure', 'RelatingBuildingStorey', 'RelatingSpatialStructure'):
                    struct = getattr(rel, attr, None)
                    if struct is not None and struct.is_a('IfcBuildingStorey'):
                        return struct
    except Exception:
        pass

    # 4) Scan storeys and their element containment relations
    try:
        for storey in model.by_type('IfcBuildingStorey'):
            if hasattr(storey, 'ContainsElements'):
                for rel in storey.ContainsElements:
                    elems = getattr(rel, 'RelatedElements', ())
                    if space in elems:
                        return storey
            if hasattr(storey, 'IsDecomposedBy'):
                for rel in storey.IsDecomposedBy:
                    if getattr(rel, 'RelatedObjects', None) is not None and space in rel.RelatedObjects:
                        return storey
    except Exception:
        pass

    return None

aud = "[FAIL] "
multi= "[FAIL] "
library= "[FAIL] "
cafe= "[FAIL] "
atrium= "[FAIL] "
office = 0
total_area = 0
for space in spaces:
    space_area = get_area(space)
    storey = get_storey(space, file)
    area_str = f"{round(space_area,2)}m2" if space_area is not None else 'N/A'
    total_area += space_area if space_area is not None else 0
    if ("auditorium" in space.LongName.lower()):
        aud = "[PASS] " + space.LongName +"\t" + area_str
    if ("cafe" in space.LongName.lower()):
        cafe = "[PASS] " + space.LongName +"\t" + area_str
    if ("library" in space.LongName.lower()):
        if space_area is not None and space_area >= 100:
            library = "[PASS] " + space.LongName +"\t" + area_str
        else :
            library = "[FAIL] " + space.LongName +"\t" + area_str + " (too small)"
    if ("atrium" in space.LongName.lower()):
        atrium = "[PASS] " + space.LongName +"\t" + area_str
    if ("office" in space.LongName.lower()):
        office += space_area if space_area is not None else 0
    if ("multi" in space.LongName.lower()):
        if space_area is not None and space_area >= 250:
            multi = "[PASS] " + space.LongName +"\t" + area_str
        else :
            multi = "[FAIL] " + space.LongName +"\t" + area_str + " (too small)"
    print(f"{space.GlobalId} : {space.Name} \t ({area_str})  \t{space.LongName}\t{storey.Name if storey else 'No Storey'}")


print("Test 01 Sche = "+ schema)
print("Test 02 Audi = "+ aud)
print("Test 03 Mult = "+ multi)
print("Test 04 Libr = "+ library)
print("Test 05 cafe = "+ cafe)
print("Test 06 Atri = "+ atrium)
print("total office = "+ str(round(office, 2))+" m2")
print("total area = "+ str(round(total_area, 2))+" m2")