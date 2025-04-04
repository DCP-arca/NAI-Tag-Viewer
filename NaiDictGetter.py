from PIL import Image
import json

from stealth_pnginfo import read_info_from_image_stealth

TARGETKEY_NAIDICT_OPTION = ("steps", "height", "width",
                            "scale", "seed", "sampler", "n_samples", "sm", "sm_dyn",
                            # WebUI options
                            "cfg scale", "cfg_scale", "clip skip", "clip_skip", "schedule type", "schedule_type", 
                            "size", "model", "model hash", "model_hash", "denoising strength", "denoising_strength")

WEBUI_OPTION_MAPPING = {
    "cfg scale": "scale",
    "cfg_scale": "scale",
    "clip skip": "clip_skip",
    "clip_skip": "clip_skip",
    "schedule type": "schedule_type",
    "schedule_type": "schedule_type",
    "model hash": "model_hash",
    "model_hash": "model_hash",
    "denoising strength": "denoising_strength",
    "denoising_strength": "denoising_strength"
}

def _get_infostr_from_img(img):
    exif = None
    pnginfo = None

    # exif
    if img.info:
        try:
            exif = json.dumps(img.info)
        except Exception as e:
            print(e)

    # stealth pnginfo
    try:
        pnginfo = read_info_from_image_stealth(img)
    except Exception as e:
        print(e)

    return exif, pnginfo

def is_nai_exif(info_str):
    """nai 이미지면 exif의 원본 JSON에 'Comment' 키가 존재하고 None이 아닌 경우 True를 반환"""
    if not info_str:
        return False
    try:
        data = json.loads(info_str)
        return 'Comment' in data and data['Comment'] is not None
    except Exception as e:
        return False

def _get_exifdict_from_infostr(info_str):
    if not info_str:
        return None
    try:
        data = json.loads(info_str)
        # WebUI 형식의 경우 'parameters' 키가 존재함
        if 'parameters' in data:
            return parse_webui_exif(data['parameters'])
        # nai 이미지라면 여기서 처리하지 않고 get_naidict_from_img에서 old 방식으로 처리함
        elif 'Comment' in data:
            return None
        else:
            return data
    except Exception as e:
        print("EXIF dictionary conversion error:", e)
        return None

def parse_webui_exif(parameters_str):
    """
    WebUI EXIF의 'parameters' 문자열을 파싱합니다.
    """
    lines = parameters_str.splitlines()
    if not lines:
        return {}
    
    # Negative prompt 라인을 찾음
    neg_prompt_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("Negative prompt:"):
            neg_prompt_index = i
            break
    
    # 프롬프트 추출 (Negative prompt 전까지의 모든 줄)
    if neg_prompt_index > 0:
        prompt = "\n".join(lines[:neg_prompt_index]).strip()
        negative_prompt = lines[neg_prompt_index][len("Negative prompt:"):].strip()
        option_lines = lines[neg_prompt_index+1:]
    else:
        # Negative prompt가 없는 경우
        prompt = "\n".join(lines).strip()
        negative_prompt = ""
        option_lines = []
    
    options = {}
    etc = {}
    
    # 옵션 파싱
    for line in option_lines:
        line = line.strip()
        parts = line.split(',')
        for part in parts:
            part = part.strip()
            if ':' in part:
                key, value = part.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                # 숫자 변환 시도
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except:
                    pass
                
                if key in WEBUI_OPTION_MAPPING:
                    key = WEBUI_OPTION_MAPPING[key]
                
                if key.lower() in [k.lower() for k in TARGETKEY_NAIDICT_OPTION]:
                    options[key] = value
                else:
                    etc[key] = value
            elif part:
                etc[part] = ""
    
    return {
        "prompt": prompt,
        "uc": negative_prompt,  # NAI 호환을 위해 "uc" 사용
        "negative_prompt": negative_prompt,  # WebUI 표준 키도 유지
        **options,  # 옵션 평탄화
        **etc  # 기타 필드 평탄화
    }

def _get_naidict_from_exifdict(exif_dict):
    try:
        nai_dict = {}
        
        # 프롬프트 처리 (None인 경우 빈 문자열로)
        nai_dict["prompt"] = (exif_dict.get("prompt") or "").strip()
        
        # 네거티브 프롬프트 처리
        if "uc" in exif_dict and exif_dict.get("uc") is not None:
            nai_dict["negative_prompt"] = (exif_dict.get("uc") or "").strip()
        elif "negative_prompt" in exif_dict and exif_dict.get("negative_prompt") is not None:
            nai_dict["negative_prompt"] = (exif_dict.get("negative_prompt") or "").strip()
        else:
            nai_dict["negative_prompt"] = ""
        
        # 옵션 추출
        option_dict = {}
        for key in TARGETKEY_NAIDICT_OPTION:
            if key in exif_dict and exif_dict[key] is not None:
                option_dict[key] = exif_dict[key]
        
        # WebUI 옵션 매핑
        for webui_key, nai_key in WEBUI_OPTION_MAPPING.items():
            if webui_key in exif_dict and exif_dict[webui_key] is not None:
                option_dict[nai_key] = exif_dict[webui_key]
        
        nai_dict["option"] = option_dict
        
        # 기타 정보 처리
        etc_dict = {}
        excluded_keys = list(TARGETKEY_NAIDICT_OPTION) + ["prompt", "uc", "negative_prompt"]
        excluded_keys.extend(WEBUI_OPTION_MAPPING.keys())
        
        for key in exif_dict.keys():
            if key not in excluded_keys:
                etc_dict[key] = exif_dict[key]
        
        nai_dict["etc"] = etc_dict
        
        return nai_dict
    except Exception as e:
        print("Error in _get_naidict_from_exifdict:", e)
    return None

def get_naidict_from_file(src):
    try:
        img = Image.open(src)
        img.load()
    except Exception as e:
        print(e)
        return None, 0
    return get_naidict_from_img(img)

def get_naidict_from_img(img):
    exif, pnginfo = _get_infostr_from_img(img)
    if not exif and not pnginfo:
        return None, 0

    # 먼저 nai 이미지 여부를 검사하여, nai 이미지면 old 방식으로 처리
    for info_str in [exif, pnginfo]:
        if is_nai_exif(info_str):
            try:
                data = json.loads(info_str)
                nai_exif = json.loads(data['Comment'])
                nd = _get_naidict_from_exifdict(nai_exif)
                if nd:
                    return nd, 3
            except Exception as e:
                print("Error in nai old method extraction:", e)

    # nai 이미지가 아니라면 WebUI 방식(new)으로 처리
    ed1 = _get_exifdict_from_infostr(exif)
    ed2 = _get_exifdict_from_infostr(pnginfo)
    if not ed1 and not ed2:
        return exif or pnginfo, 1

    nd1 = _get_naidict_from_exifdict(ed1) if ed1 else None
    nd2 = _get_naidict_from_exifdict(ed2) if ed2 else None
    if not nd1 and not nd2:
        return exif or pnginfo, 2

    if nd1:
        return nd1, 3
    else:
        return nd2, 3

if __name__ == "__main__":
    src = "target.webp"
    nd = get_naidict_from_file(src)
    print(nd)
