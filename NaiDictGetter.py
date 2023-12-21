from PIL import Image
import json
from stealth_pnginfo import read_info_from_image_stealth

TARGETKEY_NAIDICT_OPTION = ("steps", "height", "width",
                            "scale", "seed", "sampler", "n_samples", "sm", "sm_dyn")


def get_infostr_from_file(src):
    # get image
    try:
        im = Image.open(src)
        im.load()
    except Exception as e:
        print(e)
        return None

    # exif
    if im.info:
        return json.dumps(im.info)

    # stealth pnginfo
    try:
        gi = read_info_from_image_stealth(im)
        return gi
    except Exception as e:
        print(e)

    return None


def get_exifdict_from_infostr(info_str):
    try:
        comment_str = json.loads(info_str)['Comment']
        exif_dict = json.loads(comment_str)
        return exif_dict
    except Exception as e:
        print(e)
        return None


def get_naidict_from_exifdict(exif_dict):
    nai_dict = {}

    try:
        nai_dict["prompt"] = exif_dict["prompt"].strip()
    except Exception as e:
        print(e)
        pass

    try:
        nai_dict["negative_prompt"] = exif_dict["uc"].strip()
    except Exception as e:
        print(e)
        pass

    option_dict = {}
    for key in TARGETKEY_NAIDICT_OPTION:
        if key in exif_dict.keys():
            option_dict[key] = exif_dict[key]
    nai_dict["option"] = option_dict

    etc_dict = {}
    for key in exif_dict.keys():
        if key in TARGETKEY_NAIDICT_OPTION + ("uc", "prompt"):
            continue
        etc_dict[key] = exif_dict[key]
    nai_dict["etc"] = etc_dict

    return nai_dict


def get_naidict_from_file(src):
    try:
        info_str = get_infostr_from_file(src)
        if info_str == {}:
            return None, 0
    except Exception as e:
        print(e)
        return None, 0

    try:
        exif_dict = get_exifdict_from_infostr(info_str)
    except Exception as e:
        print(e)
        return info_str, 1

    try:
        nai_dict = get_naidict_from_exifdict(exif_dict)
    except Exception as e:
        print(e)
        return info_str, 2

    return nai_dict, 3


if __name__ == "__main__":
    src = "target.png"

    # info_str = get_infostr_from_file(src)
    # exif_dict = get_exifdict_from_infostr(info_str)
    # nai_dict = get_naidict_from_exifdict(exif_dict)

    nai_dict, errcode = get_naidict_from_file(src)
    print(errcode)
    print(nai_dict["prompt"])
    print(nai_dict["negative_prompt"])
    print(nai_dict["option"])
    print(nai_dict["etc"])
