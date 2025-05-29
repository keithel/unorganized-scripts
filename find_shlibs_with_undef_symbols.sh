#!/bin.bash

vsb="/path/to/vxworks/vsb/"
vxe="/vxe/to/inspect/symbols/of/"
direct_needed_libs=$(wr-readelf -d $vxe | awk '/(NEEDED)/{print substr($5,2,length($5)-2)}')

declare -a direct_needed_libpaths
for lib in $direct_needed_libs; do
    found_path=$(find "$vsb" -type f -name "$lib" -print -quit 2>/dev/null)
    if [ -n $found_path ]; then
        echo "Found $found_path"
        direct_needed_libpaths+=("$found_path")
    fi
done
direct_needed_libpaths+=("$vsb/usr/3pp/develop/usr/lib/libicudata.so.73")
direct_needed_libpaths+=("$vsb/usr/root/llvm/bin/libgfxFslVivVDK.so.1")

echo "Remaining undefined symbols:"
undefined_symbols=$(nm -u $vxe | awk '{print $2}')
for symbol in $undefined_symbols; do
    found_symbol=0
    for sl in "${direct_needed_libpaths[@]}"; do
        wr-nm --defined-only $sl | grep $symbol >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            found_symbol=1
            #echo $sl contains $symbol;
        fi
    done

    if [[ $found_symbol -eq 0 ]]; then
        echo $symbol
    fi
done
