import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)

def create_document():
    doc = docx.Document()

    # Set Margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Styles & Colors
    NAVY = RGBColor(27, 54, 93)
    SLATE = RGBColor(70, 80, 95)
    CHARCOAL = RGBColor(40, 40, 40)
    DARK_BLUE = RGBColor(15, 76, 129)

    # Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run("Landsat Stacker: The Complete Layman's Guide")
    run_title.font.name = 'Calibri'
    run_title.font.size = Pt(26)
    run_title.font.bold = True
    run_title.font.color.rgb = NAVY

    # Subtitle
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_sub = p_sub.add_run("Everything you need to know, learn, and teach satellite image stacking in simple terms.")
    run_sub.font.name = 'Calibri'
    run_sub.font.size = Pt(13)
    run_sub.font.italic = True
    run_sub.font.color.rgb = SLATE

    doc.add_paragraph() # Spacer

    # Helper function for headings
    def add_h1(text):
        h = doc.add_paragraph()
        run = h.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(18)
        run.font.bold = True
        run.font.color.rgb = NAVY
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(6)
        return h

    def add_h2(text):
        h = doc.add_paragraph()
        run = h.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = DARK_BLUE
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(4)
        return h

    def add_body(text, bold_prefix="", italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_bold = p.add_run(bold_prefix)
            r_bold.font.name = 'Calibri'
            r_bold.font.size = Pt(11)
            r_bold.font.bold = True
            r_bold.font.color.rgb = CHARCOAL
        r = p.add_run(text)
        r.font.name = 'Calibri'
        r.font.size = Pt(11)
        r.font.italic = italic
        r.font.color.rgb = CHARCOAL
        return p

    def add_bullet(bold_prefix, text):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        r_bold = p.add_run(bold_prefix)
        r_bold.font.name = 'Calibri'
        r_bold.font.size = Pt(11)
        r_bold.font.bold = True
        r_bold.font.color.rgb = CHARCOAL
        r = p.add_run(text)
        r.font.name = 'Calibri'
        r.font.size = Pt(11)
        r.font.color.rgb = CHARCOAL
        return p

    # --- SECTION 1: THE BIG PICTURE ---
    add_h1("1. The Big Picture (What is this project?)")
    add_body(
        "Imagine a satellite orbiting Earth thousands of kilometers high. Instead of taking just one regular photo like a smartphone, "
        "the Landsat satellite takes 7 separate photographs of the exact same location at the exact same time—each through a different 'filter' or 'lens'."
    )
    add_body(
        "Each photo is called a Band. By itself, a single band is just a Black and White image representing light intensity in that specific wavelength (like Red, Blue, Green, or Heat/Infrared)."
    )
    add_body(
        "What is Landsat Stacker? It is an automated Python tool that takes these 7 separate black-and-white satellite photos, checks that they align perfectly, and 'stacks' them into a single, multi-layered 3D file (.img) along with an instant, vibrant full-color preview image (.png)."
    )

    # Callout box
    table_callout = doc.add_table(rows=1, cols=1)
    table_callout.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table_callout.cell(0, 0)
    set_cell_background(cell, "F0F4F8")
    p_c = cell.paragraphs[0]
    p_c.paragraph_format.space_before = Pt(6)
    p_c.paragraph_format.space_after = Pt(6)
    r_c_bold = p_c.add_run("💡 The Sandwich Analogy: ")
    r_c_bold.font.bold = True
    r_c_bold.font.color.rgb = NAVY
    r_c = p_c.add_run(
        "Think of the 7 satellite bands as 7 single ingredients (bread, cheese, lettuce, tomato, etc.). "
        "Stacking is like putting all 7 ingredients together into a complete sandwich. Now, whenever you open the sandwich file, "
        "you can look at any layer you want or blend them together to see full color!"
    )
    r_c.font.italic = True
    doc.add_paragraph()

    # --- SECTION 2: WHY OUTPUT LOOKS BLACK & WHITE INITIALLY ---
    add_h1("2. Why Did My Output Look Black & White Originally?")
    add_body(
        "This is the #1 question most students and beginners ask! Here is the simple explanation to teach anyone:"
    )
    add_bullet("1. Single Bands are Monochrome: ", "A single file (like Band 1 or Band 4) only measures ONE light wavelength. Without Red, Green, and Blue working together, a computer screen can only display it as grayscale (black, gray, and white).")
    add_bullet("2. GIS Software Needs Instructions: ", "When you open a stacked file (.img) in GIS software (QGIS, ArcGIS, or ERDAS Imagine), the software sees 7 layers of numbers. By default, it doesn't know which layer is Red, which is Green, and which is Blue. So it just displays Layer 1 in black and white until you map the colors yourself.")

    # --- SECTION 3: UNDERSTANDING THE 7 BANDS ---
    add_h1("3. Understanding the 7 Landsat Bands")
    add_body("Here is what each layer in your Landsat stack actually represents:")

    # Table of Bands
    table = doc.add_table(rows=8, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    headers = ["Output Layer", "Landsat Band", "What It Sees / Best Used For"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        set_cell_background(cell, "1B365D")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    band_data = [
        ("Band 1", "B1 - Deep Blue", "Coastal waters, atmosphere, smoke, aerosol particles"),
        ("Band 2", "B2 - Blue", "Deep water mapping, distinguishing soil from vegetation"),
        ("Band 3", "B3 - Green", "Healthy green plants, tree canopy, water clarity"),
        ("Band 4", "B4 - Red", "Plant species differentiation, built-up urban structures"),
        ("Band 5", "B5 - Near Infrared (NIR)", "Plant health/biomass (plants reflect NIR strongly!)"),
        ("Band 6", "B6 - SWIR 1", "Soil moisture, rock types, cloud vs. snow identification"),
        ("Band 7", "B7 - SWIR 2", "Mineral mapping, geological formations, fires/burn scars")
    ]

    for row_idx, data in enumerate(band_data, start=1):
        for col_idx, text in enumerate(data):
            cell = table.cell(row_idx, col_idx)
            if row_idx % 2 == 1:
                set_cell_background(cell, "F9FAFC")
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            r = p.add_run(text)
            r.font.size = Pt(10)

    doc.add_paragraph()

    # --- SECTION 4: HOW THE PYTHON CODE WORKS STEP-BY-STEP ---
    add_h1("4. How the Python Script Works (Step-by-Step)")
    add_body("The script `Landsat_Stacker.py` performs 5 automatic steps under the hood:")

    add_h2("Step 1: Finding the Input Files (The File Inspector)")
    add_body("Scans the `input/` folder using Regex pattern matching to find files ending in `_B1.TIF` through `_B7.TIF`. It ignores extra files like quality assessment masks (`QA_PIXEL`). If any of the 7 bands are missing, it stops immediately and alerts you.")

    add_h2("Step 2: Validating Geometry & Maps (The Quality Inspector)")
    add_body("Before stacking, it verifies 4 critical checks to ensure data integrity:")
    add_bullet("• Dimensions: ", "All 7 photos must have identical Width and Height (number of pixels).")
    add_bullet("• CRS (Coordinate Reference System): ", "All 7 photos must share the exact same map projection (e.g., UTM Zone 45N).")
    add_bullet("• Pixel Size & Geotransform: ", "Each pixel must represent the exact same geographical area (e.g., 30m x 30m ground space).")

    add_h2("Step 3: Stacking & 8-Bit Contrast Stretching (The Assembly Line)")
    add_body("Raw satellite data comes in 16-bit integers (values from 0 to 65,535), which often look very dark and muddy on standard computer screens.")
    add_body("The script calculates a 2% to 98% percentile land contrast stretch. This brightens the land, removes atmospheric haze, converts the data into an 8-bit range (1 to 255), and stacks all 7 bands into `output/Landsat_Stacked.img` using the industry-standard ERDAS Imagine (HFA) format.")

    add_h2("Step 4: Quality & Integrity Check (The Auditor)")
    add_body("Opens the created `.img` file to verify that all 7 bands exist, valid map coordinates are stored, statistical tags (min/max/mean) are attached, and no band is empty or corrupt.")

    add_h2("Step 5: Automatic Full-Color Preview Generation (The Photo Printer)")
    add_body("Combines Band 4 (Red), Band 3 (Green), and Band 2 (Blue) into a true 3-channel RGB image and saves `output/Landsat_TrueColor_Preview.png`. You can double-click this PNG file to view it instantly in Windows Photo Viewer without needing GIS software!")

    # --- SECTION 5: HOW TO VIEW COLOR IN GIS SOFTWARE ---
    add_h1("5. How to View Full Color in GIS Software")
    add_body("When you import `Landsat_Stacked.img` into QGIS or ArcGIS Pro, follow these quick clicks to see full color:")

    add_h2("In QGIS:")
    add_bullet("1. ", "Right-click `Landsat_Stacked.img` layer > Properties.")
    add_bullet("2. ", "Select the Symbology tab.")
    add_bullet("3. ", "Change Render Type to 'Multiband color'.")
    add_bullet("4. ", "Set Red Band = Band 4, Green Band = Band 3, Blue Band = Band 2.")
    add_bullet("5. ", "Under Contrast Enhancement, select 'Stretch to MinMax' and click OK.")

    add_h2("In ArcGIS Pro:")
    add_bullet("1. ", "Select the `Landsat_Stacked.img` layer in Contents.")
    add_bullet("2. ", "Go to Raster Layer > Appearance > Symbology.")
    add_bullet("3. ", "Select Primary Symbology = RGB.")
    add_bullet("4. ", "Set Red = Band 4, Green = Band 3, Blue = Band 2.")

    add_h2("Popular Color Combinations to Teach:")
    add_bullet("• True Color (Natural Look - RGB 4-3-2): ", "Shows rivers, forests, cities, and land as human eyes see them from space.")
    add_bullet("• False Color Vegetation (RGB 5-4-3): ", "Healthy plants appear in glowing RED because plants reflect Near Infrared (Band 5) very strongly.")
    add_bullet("• Shortwave Infrared (RGB 7-6-4): ", "Urban cities look light blue/purple, forests look green, and water looks black.")

    # --- SECTION 6: CHEAT SHEET & SUMMARY FOR TEACHING ---
    add_h1("6. Quick Terminology Cheat Sheet (For Teaching Others)")

    add_bullet("Raster: ", "A grid of square pixels, where each pixel holds a numerical value (like a digital camera photograph with spatial coordinates).")
    add_bullet("Band: ", "A single layer of raster data representing one specific wavelength of electromagnetic light.")
    add_bullet("Band Stacking: ", "Merging multiple single-band rasters into one multi-band file so all channels are perfectly aligned.")
    add_bullet("Geotransform: ", "The math formulas that link pixels on your screen to exact GPS coordinates on Earth.")
    add_bullet("True Color Composite: ", "Combining Red, Green, and Blue bands in their natural color channels.")
    add_bullet("False Color Composite: ", "Assigning invisible light wavelengths (like Infrared) to Red/Green/Blue color channels so humans can see hidden patterns.")

    # Footer/Save
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Landsat_Stacker_Guide.docx")
    doc.save(output_path)
    print(f"Document created successfully at: {output_path}")

if __name__ == "__main__":
    create_document()
